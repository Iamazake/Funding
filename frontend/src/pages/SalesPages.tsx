import { AlertTriangle, ArrowLeft, Banknote, Landmark, Plus, RotateCcw, Search, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { OperationalBankValidationPage } from "@/components/funding/OperationalBankValidationPage";
import { RefinancingModal, type RefinancingFormInput } from "@/components/funding/RefinancingModal";
import { RemoCapitalEntryModal, type RemoCapitalInput } from "@/components/funding/RemoCapitalEntryModal";
import { SaleFundingAllocationModal, type SaleAllocationInput } from "@/components/funding/SaleFundingAllocationModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useAuth } from "@/contexts/AuthContext";
import { formatDate, formatPercentage } from "@/lib/formatters";
import { formatOperationalMoney, formatOperationalRate } from "@/lib/operationalFormat";
import { fundingApi } from "@/services/fundingApi";
import { debtContinuityApi } from "@/services/debtContinuityApi";
import { collectionView, getSale, getSales } from "@/services/operationalApi";
import type { FundingAllocation, SaleFundingComposition } from "@/types/fundingApi";
import type { QualityMessage, SaleItem, SalesFilters } from "@/types/operational";

const PAGE_SIZE = 25;

function QualityIndicator({ row }: { row: SaleItem }) {
  if (row.divergence_count > 0) return <span className="font-medium text-rose-400">{row.divergence_count} divergência(s)</span>;
  if (row.warning_count > 0) return <span className="text-amber-400">{row.warning_count} aviso(s)</span>;
  return <span className="text-muted-foreground">Sem avisos</span>;
}

function FundingCell({ row }: { row: SaleItem }) {
  if (row.funding_status === "NOT_INFORMED") return <span className="text-muted-foreground">Não informado</span>;
  return <div className="space-y-1"><StatusBadge status={row.funding_status} /><p className="text-xs text-muted-foreground">{formatOperationalMoney(row.funding_identified_amount)} · {row.funding_source_count} fonte(s)</p></div>;
}

export function SalesPage({ navigate }: { navigate: (path: string) => void }) {
  const [filters, setFilters] = useState<SalesFilters>({ page: 1, page_size: PAGE_SIZE, sort_by: "operation_date", sort_order: "desc" });
  const loader = useCallback(() => getSales(filters), [filters]);
  const { state, reload } = useAsyncData(loader);
  const hasFilters = Boolean(filters.search || filters.contract || filters.client || filters.status || filters.period_from || filters.period_to || filters.quality);
  const view = collectionView(state.status, state.status === "success" ? state.data.pagination.total : 0, hasFilters);
  const update = (values: Partial<SalesFilters>) => setFilters((current) => ({ ...current, ...values, page: values.page ?? 1 }));

  return <div className="space-y-6">
    <PageHeader eyebrow="Vendas · dados operacionais" title="Operações de crédito" description="Contratos reais provenientes de DFEN_CONTRATO e complementados por ECON_EMPRESTIMOS." actions={<Button variant="outline" onClick={() => navigate("/vendas/validacao-bancaria")}>Validação bancária</Button>} />
    {state.status === "success" && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={WalletCards} label="Contratos e órfãos" value={String(state.data.summary.total_contracts)} /><KpiCard compact icon={Landmark} label="Principal" value={formatOperationalMoney(state.data.summary.principal)} /><KpiCard compact icon={Banknote} label="Valor liberado" value={formatOperationalMoney(state.data.summary.released_amount)} /><KpiCard compact icon={AlertTriangle} label="Com divergência" value={String(state.data.summary.divergent_contracts)} /></div>}
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-7"><FormField label="Busca"><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value })} placeholder="Contrato ou cliente" /></div></FormField><FormField label="Contrato"><Input value={filters.contract ?? ""} onChange={(event) => update({ contract: event.target.value })} /></FormField><FormField label="Cliente"><Input value={filters.client ?? ""} onChange={(event) => update({ client: event.target.value })} /></FormField><FormField label="Operação de"><Input type="date" value={filters.period_from ?? ""} onChange={(event) => update({ period_from: event.target.value })} /></FormField><FormField label="Operação até"><Input type="date" value={filters.period_to ?? ""} onChange={(event) => update({ period_to: event.target.value })} /></FormField><FormField label="Status"><Input value={filters.status ?? ""} onChange={(event) => update({ status: event.target.value })} placeholder="Status ECON" /></FormField><FormField label="Qualidade"><Select value={filters.quality ?? ""} onChange={(event) => update({ quality: event.target.value as SalesFilters["quality"] })}><option value="">Todas</option><option value="VALID">Válida</option><option value="WARNING">Com aviso</option><option value="DIVERGENT">Divergente</option><option value="INVALID">Inválida</option></Select></FormField></CardContent></Card>
    {view === "loading" && <LoadingState label="Carregando contratos operacionais…" />}
    {view === "error" && <ErrorState message={state.status === "error" ? state.error : undefined} onRetry={reload} />}
    {view === "empty" && <EmptyState title="Nenhuma venda operacional disponível" description="A promoção atual não contém contratos acessíveis." />}
    {view === "filtered-empty" && <EmptyState title="Nenhum resultado para os filtros" description="Ajuste os filtros para consultar outros contratos." />}
    {view === "success" && state.status === "success" && <>
      <SalesTable items={state.data.items} navigate={navigate} />
      <Pagination page={state.data.pagination.page} pages={state.data.pagination.pages} total={state.data.pagination.total} onPage={(page) => update({ page })} />
    </>}
  </div>;
}

function SalesTable({ items, navigate }: { items: SaleItem[]; navigate: (path: string) => void }) {
  return <>
    <div className="hidden md:block"><Card className="overflow-hidden bg-card/75"><Table className="min-w-[1040px]"><TableHeader><TableRow><TableHead className="w-[250px]">Cliente / contrato</TableHead><TableHead>Operação</TableHead><TableHead className="text-right">Valor</TableHead><TableHead>Taxa</TableHead><TableHead>Prazo</TableHead><TableHead>Funding</TableHead><TableHead>Validação</TableHead><TableHead>Status / qualidade</TableHead></TableRow></TableHeader><TableBody>{items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${row.id}`)}><TableCell><SaleIdentity row={row} navigate={navigate} /></TableCell><TableCell className="whitespace-nowrap">{formatDate(row.operation_date)}<p className="text-xs text-muted-foreground">Liberação {formatDate(row.release_date)}</p></TableCell><TableCell className="whitespace-nowrap text-right"><strong className="tabular-nums">{formatOperationalMoney(row.released_amount)}</strong><p className="text-xs text-muted-foreground">Principal {formatOperationalMoney(row.principal)}</p></TableCell><TableCell className="whitespace-nowrap font-medium" title="Taxa de juros mensal">{formatOperationalRate(row.interest_rate, true)}</TableCell><TableCell className="whitespace-nowrap">{row.term ? `${row.term} meses` : "—"}</TableCell><TableCell className="min-w-[150px]"><FundingCell row={row} /></TableCell><TableCell><StatusBadge status={row.bank_validation_status} /></TableCell><TableCell className="space-y-1.5"><StatusBadge status={row.status ?? "NÃO INFORMADO"} /><QualityIndicator row={row} /></TableCell></TableRow>)}</TableBody></Table></Card></div>
    <div className="grid gap-4 md:hidden">{items.map((row) => <Card key={row.id} className="bg-card/75"><CardContent className="space-y-4 p-4"><div className="flex items-start justify-between gap-3"><SaleIdentity row={row} navigate={navigate} /><StatusBadge status={row.bank_validation_status} /></div><div className="grid grid-cols-2 gap-3 text-sm"><SaleMetric label="Valor liberado" value={formatOperationalMoney(row.released_amount)} emphasized /><SaleMetric label="Taxa mensal" value={formatOperationalRate(row.interest_rate, true)} /><SaleMetric label="Operação" value={formatDate(row.operation_date)} /><SaleMetric label="Funding" value={row.funding_status === "NOT_INFORMED" ? "Não informado" : row.funding_status} /></div><div className="flex flex-wrap items-center gap-2"><StatusBadge status={row.status ?? "NÃO INFORMADO"} /><QualityIndicator row={row} /></div></CardContent></Card>)}</div>
  </>;
}

function SaleIdentity({ row, navigate }: { row: SaleItem; navigate: (path: string) => void }) {
  const client = row.client_name?.trim() || "Não informado";
  return <div className="min-w-0"><p className="max-w-[230px] truncate font-semibold" title={client}>{client}</p><AppLink to={`/vendas/${row.id}`} onNavigate={navigate} className="block max-w-[230px] truncate text-xs text-primary" title={row.contract_code ?? undefined}>{row.contract_code ?? "Contrato não informado"}</AppLink></div>;
}

function SaleMetric({ label, value, emphasized = false }: { label: string; value: string; emphasized?: boolean }) {
  return <div><p className="text-xs text-muted-foreground">{label}</p><p className={emphasized ? "font-semibold tabular-nums" : "font-medium"}>{value}</p></div>;
}

export function SalesDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const { user } = useAuth();
  const loader = useCallback(async () => {
    const row = await getSale(id);
    const [composition, sources] = await Promise.all([fundingApi.getSaleComposition(id), fundingApi.listSources()]);
    const balances = Object.fromEntries(await Promise.all(sources.map(async (source) => [source.id, (await fundingApi.getSourceBalance(source.id, row.operation_date ?? composition.operation_date)).balance])));
    return { row, composition, sources, balances };
  }, [id]);
  const { state, reload } = useAsyncData(loader);
  const [allocationOpen, setAllocationOpen] = useState(false); const [remoOpen, setRemoOpen] = useState(false); const [refinOpen, setRefinOpen] = useState(false); const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (state.status === "loading") return <LoadingState label="Carregando venda e composição real…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const { row, composition, sources, balances } = state.data;
  const createAllocation = async (input: SaleAllocationInput) => { setSaving(true); try { await fundingApi.createAllocation(id, input); setAllocationOpen(false); setFeedback({ tone: "success", message: "Fonte adicionada e ledger registrado atomicamente." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao adicionar fonte." }); } finally { setSaving(false); } };
  const registerRemo = async (input: RemoCapitalInput) => { setSaving(true); try { await fundingApi.registerRemoCapital(input); setRemoOpen(false); setFeedback({ tone: "success", message: "Capital REMO registrado no ledger." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao registrar capital REMO." }); } finally { setSaving(false); } };
  const reverse = async (allocation: FundingAllocation) => { const reason = window.prompt("Motivo da reversão da alocação:"); if (!reason?.trim()) return; setSaving(true); try { await fundingApi.reverseAllocation(allocation.id, { reason: reason.trim() }); setFeedback({ tone: "success", message: "Alocação revertida por evento compensatório." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao reverter alocação." }); } finally { setSaving(false); } };
  const correctRefinancing = async (input: RefinancingFormInput) => { if (!row.continuity_id) return; setSaving(true); try { await debtContinuityApi.correctRefinancing(row.continuity_id, { successor_contract_code: input.successorContractCode, effective_date: input.effectiveDate, notes: input.notes }); setRefinOpen(false); setFeedback({ tone: "success", message: "Vínculo REFIN corrigido com registro de auditoria." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao corrigir REFIN." }); } finally { setSaving(false); } };
  const isRenegotiation = row.continuity_type === "RENEGOTIATION" || row.continuity_type === "ROLLOVER";
  return <div className="space-y-6">
    <AppLink to="/vendas" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Vendas</AppLink>
    <PageHeader eyebrow="Venda operacional" title={row.contract_code ?? "Contrato não informado"} description={row.client_name ?? "Não informado"} actions={<><StatusBadge status={row.data_quality_status} />{row.continuity_role && <StatusBadge status={isRenegotiation ? "RENEGOTIATION_CONFIRMED" : "REFIN"} />}<StatusBadge status={composition.funding_status} /></>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    {row.continuity_role === "PREDECESSOR" && <Card className="border-cyan-400/30 bg-cyan-400/5"><CardContent className="flex flex-wrap items-center gap-3 p-5"><StatusBadge status={isRenegotiation ? "RENEGOTIATION_CONFIRMED" : "REFIN_CONFIRMED"} /><span>{isRenegotiation ? "Renegociado para →" : "Refinanciado para →"}</span>{row.successor_sale_id ? <AppLink to={`/vendas/${row.successor_sale_id}`} onNavigate={navigate} className="font-semibold text-primary">Contrato {row.successor_contract_code ?? row.successor_sale_id}</AppLink> : <strong>Contrato {row.successor_contract_code ?? "não informado"}</strong>}{user?.role === "ADMIN" && !isRenegotiation && <Button className="ml-auto" size="sm" variant="outline" onClick={() => setRefinOpen(true)}>Corrigir vínculo</Button>}</CardContent></Card>}
    {row.continuity_role === "SUCCESSOR" && <Card className="border-cyan-400/30 bg-cyan-400/5"><CardContent className="flex flex-wrap items-center gap-3 p-5"><StatusBadge status={isRenegotiation ? "RENEGOTIATION_CONFIRMED" : "REFIN"} /><span>{isRenegotiation ? "Renegociado de" : "Refinanciado de"}</span>{row.predecessor_sale_id ? <AppLink to={`/vendas/${row.predecessor_sale_id}`} onNavigate={navigate} className="font-semibold text-primary">contrato {row.predecessor_contract_code ?? row.predecessor_sale_id}</AppLink> : <strong>contrato {row.predecessor_contract_code ?? "não informado"}</strong>}</CardContent></Card>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Banknote} label="Valor da operação" value={formatOperationalMoney(composition.operation_amount)} helper="Campo: valor liberado" /><KpiCard compact icon={WalletCards} label="Funding identificado" value={formatOperationalMoney(composition.identified_amount)} /><KpiCard compact icon={AlertTriangle} label="Diferença" value={formatOperationalMoney(composition.difference)} /><KpiCard compact icon={Landmark} label="Fontes ativas" value={String(composition.source_count)} /></div>
    <FundingCompositionPanel composition={composition} saving={saving} onAdd={() => setAllocationOpen(true)} onRegisterRemo={() => setRemoOpen(true)} onReverse={reverse} />
    <InfoGrid rows={[["Código de Contrato", row.contract_code ?? "Não informado"], ["Data da operação", formatDate(row.operation_date)], ["Data de liberação", formatDate(row.release_date)], ["Primeiro vencimento", formatDate(row.first_due_date)], ["Prazo", row.term ? `${row.term} meses` : "Não informado"], ["Principal", formatOperationalMoney(row.principal)], ["IOF", formatOperationalMoney(row.iof)], ["Valor financiado", formatOperationalMoney(row.financed_amount)], ["Valor liberado", formatOperationalMoney(row.released_amount)], ["Parcela (PMT)", formatOperationalMoney(row.installment_amount)], ["Taxa de juros mensal", formatOperationalRate(row.interest_rate, true)], ["TIR", formatOperationalRate(row.irr_rate)], ["CET mensal", formatOperationalRate(row.cet_monthly_rate, true)], ["Status", row.status ?? "Não informado"]]} />
    <QualityPanel warnings={row.warnings} divergences={row.divergences} />
    <SaleFundingAllocationModal open={allocationOpen} sources={sources} historicalBalances={balances} saving={saving} onClose={() => setAllocationOpen(false)} onSave={createAllocation} />
    <RemoCapitalEntryModal open={remoOpen} saving={saving} onClose={() => setRemoOpen(false)} onSave={registerRemo} />
    <RefinancingModal open={refinOpen} predecessorContractCode={row.contract_code} initialSuccessorContractCode={row.successor_contract_code ?? ""} correction saving={saving} onClose={() => setRefinOpen(false)} onSave={correctRefinancing} />
  </div>;
}

function FundingCompositionPanel({ composition, saving, onAdd, onRegisterRemo, onReverse }: { composition: SaleFundingComposition; saving: boolean; onAdd: () => void; onRegisterRemo: () => void; onReverse: (allocation: FundingAllocation) => void }) {
  const active = composition.allocations.filter((item) => item.status === "ACTIVE");
  return <Card className="overflow-hidden bg-card/75"><CardHeader className="flex-row items-center justify-between"><div><CardTitle className="text-base">Composição real do Funding</CardTitle><p className="mt-1 text-sm text-muted-foreground">Saldo validado em {formatDate(composition.operation_date)}. Percentual derivado do valor alocado.</p></div><div className="flex gap-2"><Button variant="outline" onClick={onRegisterRemo}>Capital REMO</Button><Button onClick={onAdd}><Plus className="size-4" />Adicionar fonte</Button></div></CardHeader><CardContent className="p-0">{active.length === 0 ? <div className="p-6"><EmptyState title="Funding ainda não informado." description="Adicione uma ou mais fontes reais; composição incompleta é permitida." /></div> : <Table><TableHeader><TableRow><TableHead>Fonte</TableHead><TableHead>Investidor / aporte</TableHead><TableHead>Valor alocado</TableHead><TableHead>Participação</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Correção</TableHead></TableRow></TableHeader><TableBody>{composition.allocations.map((allocation) => <TableRow key={allocation.id} className={allocation.status === "REVERSED" ? "opacity-50" : ""}><TableCell>{allocation.source_type === "REMO_CAPITAL" ? "Capital próprio REMO" : "Aporte de investidor"}</TableCell><TableCell>{allocation.investor_name ?? "REMO"}<p className="text-xs text-muted-foreground">{allocation.contribution_code ?? "Fonte própria"}</p></TableCell><TableCell>{formatOperationalMoney(allocation.amount)}</TableCell><TableCell>{allocation.percentage ? formatPercentage(allocation.percentage) : "—"}</TableCell><TableCell><StatusBadge status={allocation.status} /></TableCell><TableCell className="text-right">{allocation.status === "ACTIVE" && <Button size="sm" variant="ghost" disabled={saving} onClick={() => onReverse(allocation)}><RotateCcw className="size-4" />Reverter</Button>}</TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card>;
}

export function SalesDivergencesPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(() => getSales({ page: 1, page_size: 100, quality: "DIVERGENT" }), []);
  const { state, reload } = useAsyncData(loader);
  return <div className="space-y-6"><PageHeader eyebrow="Vendas" title="Divergências operacionais" description="Empréstimos sem contrato e outras divergências reais da promoção atual." />{state.status === "loading" ? <LoadingState /> : state.status === "error" ? <ErrorState message={state.error} onRetry={reload} /> : state.data.items.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato</TableHead><TableHead>Cliente</TableHead><TableHead>Status</TableHead><TableHead>Motivos</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${row.id}`)}><TableCell>{row.contract_code ?? "Não informado"}</TableCell><TableCell>{row.client_name ?? "Não informado"}</TableCell><TableCell><StatusBadge status={row.data_quality_status} /></TableCell><TableCell>{row.divergence_count} divergência(s)</TableCell></TableRow>)}</TableBody></Table></Card>}</div>;
}

export function SalesBankValidationPage({ navigate }: { navigate: (path: string) => void }) { return <div className="space-y-6"><AppLink to="/vendas" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Vendas</AppLink><OperationalBankValidationPage kind="SALE" navigate={navigate} /></div>; }

function QualityPanel({ warnings, divergences }: { warnings: QualityMessage[]; divergences: QualityMessage[] }) { return <div className="grid gap-4 lg:grid-cols-2"><Card className="bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-amber-400">Avisos ({warnings.length})</h2><div className="mt-3 space-y-2 text-sm">{warnings.length ? warnings.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhum aviso.</p>}</div></CardContent></Card><Card className="border-rose-400/30 bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-rose-400">Divergências ({divergences.length})</h2><div className="mt-3 space-y-2 text-sm">{divergences.length ? divergences.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhuma divergência.</p>}</div></CardContent></Card></div>; }
function InfoGrid({ rows }: { rows: [string, string][] }) { return <Card className="bg-card/75"><CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label}><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</CardContent></Card>; }
function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) { return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} registro(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>; }
