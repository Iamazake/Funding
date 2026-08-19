import { ArrowLeft, CircleDollarSign, Pencil, Plus, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ContributionFormModal } from "@/components/funding/ContributionFormModal";
import { InvestorFormModal } from "@/components/funding/InvestorFormModal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatMoney, formatDate } from "@/lib/formatters";
import { formatMonthlyRate } from "@/lib/fundingFormat";
import { fundingApi } from "@/services/fundingApi";
import type { FundingContributionInput, FundingInvestorInput } from "@/types/fundingApi";

export function InvestorDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(async () => ({ investor: await fundingApi.getInvestor(id), contributions: await fundingApi.listContributions(id) }), [id]);
  const { state, reload } = useAsyncData(loader);
  const [edit, setEdit] = useState(false); const [contributionOpen, setContributionOpen] = useState(false); const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (state.status === "loading") return <LoadingState label="Carregando investidor…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const { investor, contributions } = state.data;
  const total = contributions.reduce((sum, item) => sum + BigInt(item.original_amount.replace(".", "")), 0n);
  const saveInvestor = async (input: FundingInvestorInput) => { setSaving(true); try { await fundingApi.updateInvestor(id, input); setEdit(false); setFeedback({ tone: "success", message: "Investidor atualizado." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar." }); } finally { setSaving(false); } };
  const saveContribution = async (input: FundingContributionInput) => { setSaving(true); try { await fundingApi.createContribution(input); setContributionOpen(false); setFeedback({ tone: "success", message: "Aporte cadastrado." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar." }); } finally { setSaving(false); } };
  return <div className="space-y-6">
    <AppLink to="/cadastro/investidores" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar</AppLink>
    <PageHeader eyebrow="Investidor" title={investor.name} description={`${investor.code} · cadastro real`} actions={<><StatusBadge status={investor.status} /><Button variant="outline" onClick={() => setEdit(true)}><Pencil className="size-4" />Editar</Button><Button onClick={() => setContributionOpen(true)}><Plus className="size-4" />Novo aporte</Button></>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={WalletCards} label="Aportes individuais" value={String(contributions.length)} /><KpiCard compact icon={CircleDollarSign} label="Capital original" value={formatMoney(`${total / 100n}.${(total % 100n).toString().padStart(2, "0")}`)} /><KpiCard compact icon={WalletCards} label="Aportes ativos" value={String(contributions.filter((item) => item.status === "ACTIVE").length)} /></div>
    {contributions.length === 0 ? <EmptyState title="Nenhum aporte cadastrado." description="Este investidor ainda não possui aportes." /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Aporte</TableHead><TableHead>Data</TableHead><TableHead>Valor original</TableHead><TableHead>Taxa mensal</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{contributions.map((item) => <TableRow key={item.id} className="cursor-pointer" onClick={() => navigate(`/cadastro/aportes/${item.id}`)}><TableCell className="font-mono text-xs">{item.code}</TableCell><TableCell>{formatDate(item.contribution_date)}</TableCell><TableCell>{formatMoney(item.original_amount)}</TableCell><TableCell>{formatMonthlyRate(item.monthly_rate)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</TableBody></Table></Card>}
    <InvestorFormModal open={edit} investor={investor} saving={saving} onClose={() => setEdit(false)} onSave={saveInvestor} />
    <ContributionFormModal open={contributionOpen} investors={[investor]} presetInvestorId={id} saving={saving} onClose={() => setContributionOpen(false)} onSave={saveContribution} />
  </div>;
}
