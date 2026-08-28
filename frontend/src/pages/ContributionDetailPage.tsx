import { ArrowLeft, CalendarDays, CircleDollarSign, Landmark, Pencil, Percent, TrendingUp, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { ContributionFormModal } from "@/components/funding/ContributionFormModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney, formatPercent } from "@/lib/formatters";
import { formatMonthlyRate } from "@/lib/fundingFormat";
import { fundingApi } from "@/services/fundingApi";
import type { ContributionAnalysis, FundingContributionInput } from "@/types/fundingApi";

type DetailTab = "operations" | "movements" | "returns";

const entryLabels: Record<string, string> = {
  CONTRIBUTION: "Aporte", ALLOCATION: "Alocação", PRINCIPAL_RETURN: "Retorno de principal",
  REINVESTMENT: "Reinvestimento", CAPITAL_RETURN: "Devolução de capital", REVERSAL: "Estorno", ADJUSTMENT: "Ajuste",
};
const originLabels: Record<string, string> = {
  CONTRIBUTION: "Aporte", SALE_ALLOCATION: "Venda", REMO_ADMIN: "Ajuste administrativo",
  ALLOCATION_REVERSAL: "Estorno de alocação", REVENUE_DISTRIBUTION: "Receita processada",
  REVENUE_DISTRIBUTION_REVERSAL: "Estorno de Receita", FUTURE_FINANCIAL_EVENT: "Evento financeiro",
};

export function ContributionDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(async () => {
    const analysis = await fundingApi.getContributionAnalysis(id);
    return { contribution: analysis.contribution, analysis, investor: analysis.investor };
  }, [id]);
  const { state, reload } = useAsyncData(loader);
  const [tab, setTab] = useState<DetailTab>("operations");
  const [edit, setEdit] = useState(false); const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (state.status === "loading") return <LoadingState label="Carregando análise do aporte…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const { contribution, analysis, investor } = state.data; const summary = analysis.summary;
  const save = async (input: FundingContributionInput) => { setSaving(true); try { await fundingApi.updateContribution(id, input); setEdit(false); setFeedback({ tone: "success", message: "Aporte atualizado e alteração auditada." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar aporte." }); } finally { setSaving(false); } };
  return <div className="space-y-6">
    <AppLink to="/cadastro/aportes" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar</AppLink>
    <PageHeader eyebrow="Detalhe analítico do aporte" title={summary.contribution_code} description={`Capital aportado por ${summary.investor_name}.`} actions={<><StatusBadge status={summary.status} /><Button variant="outline" onClick={() => setEdit(true)}><Pencil className="size-4" />Editar</Button></>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard compact icon={CircleDollarSign} label="Valor original" value={formatMoney(summary.original_amount)} />
      <KpiCard compact icon={WalletCards} label="Saldo disponível" value={formatMoney(summary.available_balance)} helper="Derivado do ledger" />
      <KpiCard compact icon={Landmark} label="Capital alocado" value={formatMoney(summary.allocated_capital)} helper="Somente allocations ativas" />
      <KpiCard compact icon={TrendingUp} label="Principal retornado" value={formatMoney(summary.returned_principal)} helper="PRINCIPAL_RETURN sem estorno" />
      <KpiCard compact icon={CircleDollarSign} label="Capital exposto" value={formatMoney(summary.exposed_capital)} />
      <KpiCard compact icon={Percent} label="Utilização" value={formatPercent(summary.utilization_percentage)} helper="Exposto ÷ valor original" />
      <KpiCard compact icon={Percent} label="Taxa contratual" value={formatMonthlyRate(summary.monthly_rate)} />
      <KpiCard compact icon={CalendarDays} label="Data do aporte" value={formatDate(summary.contribution_date)} />
      <KpiCard compact icon={CalendarDays} label="Vencimento do aporte" value={contribution.end_date ? formatDate(contribution.end_date) : "Não informado"} helper="A data não registra devolução automática" />
    </div>
    <Tabs items={[{ value: "operations", label: "Operações financiadas" }, { value: "movements", label: "Movimentações" }, { value: "returns", label: "Retornos" }]} value={tab} onChange={(value) => setTab(value as DetailTab)} />
    {tab === "operations" && <OperationsSection analysis={analysis} navigate={navigate} />}
    {tab === "movements" && <MovementsSection analysis={analysis} />}
    {tab === "returns" && <ReturnsSection analysis={analysis} navigate={navigate} />}
    <ContributionFormModal open={edit} contribution={contribution} investors={[investor]} saving={saving} onClose={() => setEdit(false)} onSave={save} />
  </div>;
}

function OperationsSection({ analysis, navigate }: { analysis: ContributionAnalysis; navigate: (path: string) => void }) {
  if (analysis.operations.length === 0) return <EmptyState title="Nenhuma operação financiada" description="Este aporte ainda não possui allocations." />;
  return <Card className="overflow-hidden bg-card/75"><CardHeader><CardTitle className="text-base">Participação por Venda</CardTitle></CardHeader><CardContent className="p-0"><Table className="min-w-[1280px]"><TableHeader><TableRow><TableHead>Venda / cliente</TableHead><TableHead>Tipo</TableHead><TableHead>Data</TableHead><TableHead>Valor-base</TableHead><TableHead>Alocado</TableHead><TableHead>% da operação</TableHead><TableHead>Principal retornado</TableHead><TableHead>Exposto</TableHead><TableHead>Allocation</TableHead><TableHead>Funding</TableHead></TableRow></TableHeader><TableBody>{analysis.operations.map((item) => <TableRow key={item.allocation_id} className="cursor-pointer" onClick={() => navigate(`/vendas/${item.sale_id}`)}><TableCell><AppLink to={`/vendas/${item.sale_id}`} onNavigate={navigate} className="font-semibold text-primary">{item.contract_code ?? item.sale_id}</AppLink><p className="text-xs text-muted-foreground">{item.client_name ?? "Cliente não resolvido"}</p></TableCell><TableCell>{item.sale_kind === "ORPHAN_LOAN" ? `Empréstimo órfão #${item.loan_id}` : "Contrato"}</TableCell><TableCell>{formatDate(item.operation_date)}</TableCell><TableCell>{item.operation_amount ? formatMoney(item.operation_amount) : "—"}</TableCell><TableCell>{formatMoney(item.allocated_amount)}</TableCell><TableCell>{item.operation_percentage ? formatPercent(item.operation_percentage) : "—"}</TableCell><TableCell>{formatMoney(item.returned_principal)}</TableCell><TableCell>{formatMoney(item.exposed_capital)}</TableCell><TableCell><StatusBadge status={item.allocation_status} /></TableCell><TableCell><StatusBadge status={item.funding_status} /></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}

function MovementsSection({ analysis }: { analysis: ContributionAnalysis }) {
  if (analysis.movements.length === 0) return <EmptyState title="Nenhuma movimentação" description="O ledger desta fonte ainda está vazio." />;
  return <Card className="overflow-hidden bg-card/75"><CardHeader><CardTitle className="text-base">Ledger da fonte</CardTitle></CardHeader><CardContent className="p-0"><Table className="min-w-[980px]"><TableHeader><TableRow><TableHead>Data efetiva</TableHead><TableHead>Tipo</TableHead><TableHead>Referência / origem</TableHead><TableHead>Entrada</TableHead><TableHead>Saída</TableHead><TableHead>Saldo acumulado</TableHead></TableRow></TableHeader><TableBody>{analysis.movements.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.effective_date)}</TableCell><TableCell>{entryLabels[item.entry_type] ?? item.entry_type}</TableCell><TableCell>{originLabels[item.origin_type] ?? item.origin_type}<p className="text-xs text-muted-foreground">{movementReference(item)}</p></TableCell><TableCell className="text-emerald-400">{item.inflow === "0.00" ? "—" : formatMoney(item.inflow)}</TableCell><TableCell className="text-rose-400">{item.outflow === "0.00" ? "—" : formatMoney(item.outflow)}</TableCell><TableCell className="font-semibold">{formatMoney(item.running_balance)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}

function movementReference(item: ContributionAnalysis["movements"][number]): string {
  if (item.reversal_of_entry_id) return `Movimento estornado #${item.reversal_of_entry_id}`;
  if (item.allocation_id) return `Allocation ${item.allocation_id}`;
  if (item.revenue_distribution_item_id) return `Rateio ${item.revenue_distribution_item_id}`;
  return item.notes ?? `Movimento #${item.id}`;
}

function ReturnsSection({ analysis, navigate }: { analysis: ContributionAnalysis; navigate: (path: string) => void }) {
  const totals = analysis.return_totals;
  return <div className="space-y-4"><div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={CircleDollarSign} label="Principal atribuído" value={formatMoney(totals.principal_amount)} /><KpiCard compact icon={TrendingUp} label="Juros atribuídos" value={formatMoney(totals.interest_amount)} helper="Informação econômica; não altera o saldo" /><KpiCard compact icon={CircleDollarSign} label="Descontos atribuídos" value={formatMoney(totals.discount_amount)} /></div>{analysis.returns.length === 0 ? <EmptyState title="Nenhum retorno de Receita processado para este aporte." description="Os rateios processados aparecerão aqui, sem uso de dados fictícios." /> : <Card className="overflow-hidden bg-card/75"><CardHeader><CardTitle className="text-base">Retornos por Receita</CardTitle></CardHeader><CardContent className="p-0"><Table className="min-w-[900px]"><TableHeader><TableRow><TableHead>Data</TableHead><TableHead>Venda / Receita</TableHead><TableHead>Principal</TableHead><TableHead>Juros</TableHead><TableHead>Desconto</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{analysis.returns.map((item) => <TableRow key={item.distribution_item_id}><TableCell>{formatDate(item.effective_date)}</TableCell><TableCell><AppLink to={`/vendas/${item.sale_id}`} onNavigate={navigate} className="font-semibold text-primary">{item.sale_id}</AppLink><p className="text-xs text-muted-foreground">Receita #{item.revenue_id}</p></TableCell><TableCell>{formatMoney(item.principal_amount)}</TableCell><TableCell>{formatMoney(item.interest_amount)}</TableCell><TableCell>{formatMoney(item.discount_amount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>}</div>;
}
