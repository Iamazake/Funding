import { KeyRound, Plus, UserRoundCog } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/formatters";
import { authApi } from "@/services/authApi";
import type { AppUser, UserRole } from "@/types/auth";

export function UsersPage() {
  const [users, setUsers] = useState<AppUser[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<AppUser | "new" | null>(null); const [resetting, setResetting] = useState<AppUser | null>(null); const [feedback, setFeedback] = useState<Feedback | null>(null);
  const load = async () => { setLoading(true); setError(null); try { setUsers(await authApi.listUsers()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar os usuários."); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  return <div className="space-y-6"><PageHeader eyebrow="Administração" title="Usuários" description="Cadastre operadores, altere perfis e desative acessos sem excluir o histórico." actions={<Button onClick={() => setEditing("new")}><Plus className="size-4" />Novo usuário</Button>} /><FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />{loading ? <LoadingState label="Carregando usuários…" /> : error ? <ErrorState message={error} onRetry={() => void load()} /> : <Card className="overflow-hidden"><Table><TableHeader><TableRow><TableHead>Nome</TableHead><TableHead>E-mail</TableHead><TableHead>Perfil</TableHead><TableHead>Status</TableHead><TableHead>Último acesso</TableHead><TableHead>Criado em</TableHead><TableHead>Ações</TableHead></TableRow></TableHeader><TableBody>{users.map((user) => <TableRow key={user.id}><TableCell className="font-medium">{user.name}</TableCell><TableCell>{user.email}</TableCell><TableCell><StatusBadge status={user.role} /></TableCell><TableCell><StatusBadge status={user.status} /></TableCell><TableCell>{user.last_login_at ? formatDate(user.last_login_at) : "Nunca"}</TableCell><TableCell>{formatDate(user.created_at)}</TableCell><TableCell><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEditing(user)}><UserRoundCog className="size-3" />Editar</Button><Button size="sm" variant="outline" onClick={() => setResetting(user)}><KeyRound className="size-3" />Senha</Button></div></TableCell></TableRow>)}</TableBody></Table></Card>}<UserModal user={editing} onClose={() => setEditing(null)} onSaved={async (message) => { setEditing(null); setFeedback({ tone: "success", message }); await load(); }} /><ResetModal user={resetting} onClose={() => setResetting(null)} onSaved={async () => { setResetting(null); setFeedback({ tone: "success", message: "Senha redefinida; as sessões anteriores foram revogadas." }); await load(); }} /></div>;
}

function UserModal({ user, onClose, onSaved }: { user: AppUser | "new" | null; onClose: () => void; onSaved: (message: string) => Promise<void> }) {
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [role, setRole] = useState<UserRole>("ANALYST"); const [active, setActive] = useState(true); const [error, setError] = useState<string | null>(null); const [saving, setSaving] = useState(false);
  useEffect(() => { if (user && user !== "new") { setName(user.name); setEmail(user.email); setRole(user.role); setActive(user.status === "ACTIVE"); } else { setName(""); setEmail(""); setPassword(""); setRole("ANALYST"); setActive(true); } setError(null); }, [user]);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!user) return; setSaving(true); setError(null); try { if (user === "new") await authApi.createUser({ name, email, password, role }); else await authApi.updateUser(user.id, { name, role, status: active ? "ACTIVE" : "INACTIVE" }); await onSaved(user === "new" ? "Usuário criado com sucesso." : "Usuário atualizado com sucesso."); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível salvar o usuário."); } finally { setSaving(false); } };
  return <Modal open={user !== null} title={user === "new" ? "Novo usuário" : "Editar usuário"} onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button type="submit" form="user-form" disabled={saving}>{saving ? "Salvando…" : "Salvar"}</Button></>}><form id="user-form" className="space-y-4" onSubmit={submit}>{error && <p className="text-sm text-rose-400">{error}</p>}<FormField label="Nome"><Input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} /></FormField><FormField label="E-mail"><Input required type="email" disabled={user !== "new"} value={email} onChange={(event) => setEmail(event.target.value)} /></FormField>{user === "new" && <FormField label="Senha inicial (mínimo 10 caracteres)"><Input required minLength={10} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></FormField>}<FormField label="Perfil"><Select value={role} onChange={(event) => setRole(event.target.value as UserRole)}><option value="ANALYST">Analyst</option><option value="ADMIN">Admin</option></Select></FormField>{user !== "new" && <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />Usuário ativo</label>}</form></Modal>;
}

function ResetModal({ user, onClose, onSaved }: { user: AppUser | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [password, setPassword] = useState(""); const [error, setError] = useState<string | null>(null); const [saving, setSaving] = useState(false);
  useEffect(() => { setPassword(""); setError(null); }, [user]);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!user) return; setSaving(true); setError(null); try { await authApi.resetPassword(user.id, password); await onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível redefinir a senha."); } finally { setSaving(false); } };
  return <Modal open={user !== null} title="Redefinir senha" description={user ? `Defina uma nova senha para ${user.name}.` : undefined} onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button type="submit" form="reset-form" disabled={saving}>{saving ? "Redefinindo…" : "Redefinir senha"}</Button></>}><form id="reset-form" onSubmit={submit}>{error && <p className="mb-3 text-sm text-rose-400">{error}</p>}<FormField label="Nova senha (mínimo 10 caracteres)"><Input required minLength={10} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></FormField></form></Modal>;
}
