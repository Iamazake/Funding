import { Eye, Pencil, Plus, Search, WalletCards } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ContributionFormModal } from "@/components/funding/ContributionFormModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney } from "@/lib/formatters";
import { formatMonthlyRate } from "@/lib/fundingFormat";
import { fundingApi } from "@/services/fundingApi";
import type { FundingContribution, FundingContributionInput } from "@/types/fundingApi";

export function ContributionsPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(async () => ({ investors: await fundingApi.listInvestors(), contributions: await fundingApi.listContributions() }), []);
  const { state, reload } = useAsyncData(loader);
  const [search, setSearch] = useState(""); const [status, setStatus] = useState("all"); const [editing, setEditing] = useState<FundingContribution>(); const [open, setOpen] = useState(false); const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState<Feedback | null>(null);
  const investors = useMemo(() => state.status === "success" ? state.data.investors : [], [state]);
  const contributions = useMemo(() => state.status === "success" ? state.data.contributions : [], [state]);
  const filtered = useMemo(() => contributions.filter((item) => { const investor = investors.find((value) => value.id === item.investor_id); const term = search.trim().toLocaleLowerCase("pt-BR"); return (!term || item.code.toLowerCase().includes(term) || investor?.name.toLocaleLowerCase("pt-BR").includes(term)) && (status === "all" || item.status === status); }), [contributions, investors, search, status]);
  const total = contributions.reduce((sum, item) => sum + BigInt(item.original_amount.replace(".", "")), 0n);
  const save = async (input: FundingContributionInput) => { setSaving(true); try { if (editing) await fundingApi.updateContribution(editing.id, input); else await fundingApi.createContribution(input); setOpen(false); setEditing(undefined); setFeedback({ tone: "success", message: editing ? "Aporte atualizado." : "Aporte cadastrado." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar aporte." }); } finally { setSaving(false); } };
  return <div className="space-y-6">
    <PageHeader eyebrow="Cadastro" title="Aportes" description="Aportes reais e individualizados por investidor." actions={<Button disabled={investors.length === 0} onClick={() => { setEditing(undefined); setOpen(true); }}><Plus className="size-4" />Novo aporte</Button>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    {state.status === "loading" && <LoadingState label="Carregando aportes…" />}
    {state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}
    {state.status === "success" && <>
      <div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={WalletCards} label="Aportes" value={String(contributions.length)} /><KpiCard compact icon={WalletCards} label="Aportes ativos" value={String(contributions.filter((item) => item.status === "ACTIVE").length)} /><KpiCard compact icon={WalletCards} label="Capital original" value={formatMoney(`${total / 100n}.${(total % 100n).toString().padStart(2, "0")}`)} /></div>
      {investors.length === 0 && <EmptyState title="Nenhum investidor cadastrado." description="Cadastre um investidor antes de registrar aportes." />}
      {investors.length > 0 && <><Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_200px]"><label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar aporte</span><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar aporte ou investidor…" /></label><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os status</option><option value="ACTIVE">Ativos</option><option value="INACTIVE">Inativos</option><option value="CLOSED">Encerrados</option></Select></CardContent></Card>
      {contributions.length === 0 ? <EmptyState title="Nenhum aporte cadastrado." description="Registre o primeiro aporte pela API real." /> : filtered.length === 0 ? <EmptyState title="Nenhum aporte encontrado." description="Ajuste os filtros da consulta." /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Aporte</TableHead><TableHead>Investidor</TableHead><TableHead>Data</TableHead><TableHead>Valor original</TableHead><TableHead>Taxa</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader><TableBody>{filtered.map((item) => <TableRow key={item.id}><TableCell className="font-mono text-xs">{item.code}</TableCell><TableCell>{investors.find((value) => value.id === item.investor_id)?.name ?? "—"}</TableCell><TableCell>{formatDate(item.contribution_date)}</TableCell><TableCell>{formatMoney(item.original_amount)}</TableCell><TableCell>{formatMonthlyRate(item.monthly_rate)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell><div className="flex justify-end gap-2"><Button size="sm" variant="ghost" onClick={() => { setEditing(item); setOpen(true); }}><Pencil className="size-4" /><span className="sr-only">Editar</span></Button><AppLink to={`/cadastro/aportes/${item.id}`} onNavigate={navigate}><Button size="sm" variant="outline"><Eye className="size-4" />Ver</Button></AppLink></div></TableCell></TableRow>)}</TableBody></Table></Card>}</>}
    </>}
    <ContributionFormModal open={open} contribution={editing} investors={investors} saving={saving} onClose={() => { setOpen(false); setEditing(undefined); }} onSave={save} />
  </div>;
}
