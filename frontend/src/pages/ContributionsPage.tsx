import { Ban, Eye, Pencil, Plus, Search } from "lucide-react";
import { useState } from "react";
import { AppLink } from "@/components/app/AppLink";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ContributionFormModal } from "@/components/funding/ContributionFormModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCentsAmount, formatDate } from "@/lib/formatters";
import { fundingRepository, useFundingState } from "@/services/fundingService";
import type { Contribution, ContributionInput } from "@/types/funding";

export function ContributionsPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState(); const [search, setSearch] = useState(""); const [status, setStatus] = useState("all"); const [editing, setEditing] = useState<Contribution>(); const [open, setOpen] = useState(false); const [cancel, setCancel] = useState<Contribution | null>(null); const [feedback, setFeedback] = useState<Feedback | null>(null);
  const investorName = (id: string) => state.investors.find((item) => item.id === id)?.name ?? "—";
  const rows = state.contributions.filter((item) => `${item.code} ${investorName(item.investorId)}`.toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR")) && (status === "all" || item.status === status));
  const save = (input: ContributionInput) => { try { if (editing) fundingRepository.updateContribution(editing.id, input); else fundingRepository.createContribution(input); setOpen(false); setEditing(undefined); setFeedback({ tone: "success", message: editing ? "Aporte atualizado." : "Aporte e entrada de tesouraria criados." }); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar." }); } };
  return <div className="space-y-6"><PageHeader eyebrow="Cadastro" title="Aportes" description="Múltiplos aportes por investidor, com taxa em basis points e cálculo inteiro sobre o valor originalmente aportado." actions={<Button onClick={() => { setEditing(undefined); setOpen(true); }}><Plus className="size-4" />Novo aporte</Button>} /><FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_240px]"><label className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Código ou investidor…" /></label><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os status</option>{["PENDENTE", "ATIVO", "PARCIALMENTE_ALOCADO", "TOTALMENTE_ALOCADO", "EM_LIQUIDACAO", "LIQUIDADO", "CANCELADO"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</Select></CardContent></Card>
    {rows.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Aporte</TableHead><TableHead>Investidor</TableHead><TableHead>Status</TableHead><TableHead>Original</TableHead><TableHead>Disponível</TableHead><TableHead>Alocado</TableHead><TableHead>Remuneração mensal</TableHead><TableHead>Vigência</TableHead><TableHead>Ações</TableHead></TableRow></TableHeader><TableBody>{rows.map((item) => <TableRow key={item.id}><TableCell><AppLink to={`/cadastro/aportes/${item.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{item.code}</AppLink></TableCell><TableCell>{investorName(item.investorId)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{formatCentsAmount(item.originalAmount)}</TableCell><TableCell>{formatCentsAmount(item.availableBalance)}</TableCell><TableCell>{formatCentsAmount(item.allocatedBalance)}</TableCell><TableCell>{formatCentsAmount(item.expectedMonthlyRemuneration)}<p className="text-xs text-muted-foreground">{item.monthlyRateBps} bps · base original</p></TableCell><TableCell>{formatDate(item.startDate)} – {formatDate(item.endDate)}</TableCell><TableCell><div className="flex gap-1"><Button size="icon" variant="ghost" onClick={() => navigate(`/cadastro/aportes/${item.id}`)}><Eye className="size-4" /></Button><Button size="icon" variant="ghost" onClick={() => { setEditing(item); setOpen(true); }}><Pencil className="size-4" /></Button>{item.status !== "CANCELADO" && <Button size="icon" variant="ghost" onClick={() => setCancel(item)}><Ban className="size-4" /></Button>}</div></TableCell></TableRow>)}</TableBody></Table></Card>}
    <ContributionFormModal open={open} contribution={editing} investors={state.investors} onClose={() => setOpen(false)} onSave={save} /><ConfirmDialog open={cancel !== null} title="Cancelar aporte?" description="O registro e seu histórico serão preservados." confirmLabel="Cancelar aporte" danger onCancel={() => setCancel(null)} onConfirm={() => { if (cancel) fundingRepository.setContributionStatus(cancel.id, "CANCELADO"); setCancel(null); }} />
  </div>;
}
