import { AlertTriangle, Banknote, Landmark, ReceiptText, Search, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatPercentage } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import { collectionView, getRevenue } from "@/services/operationalApi";
import type { RevenueFilters, RevenueItem } from "@/types/operational";

const PAGE_SIZE = 25;
const QUICK_FILTERS: Array<{ value: NonNullable<RevenueFilters["view"]>; label: string }> = [
  { value: "all", label: "Todos" },
  { value: "received", label: "Recebidos" },
  { value: "open", label: "Em aberto" },
  { value: "overdue", label: "Em atraso" },
  { value: "future", label: "Futuros" },
];

function QualityIndicator({ row }: { row: RevenueItem }) {
  if (row.divergence_count > 0) return <span className="font-semibold text-rose-400">{row.divergence_count} divergência(s)</span>;
  if (row.warning_count > 0) return <span className="text-amber-400">{row.warning_count} aviso(s)</span>;
  return null;
}

function RevenueSituation({ row }: { row: RevenueItem }) {
  return <div className="space-y-1.5"><StatusBadge status={row.installment_status === "REFIN" ? "REFIN" : row.situation ?? row.installment_status ?? "NÃO INFORMADA"} /><QualityIndicator row={row} /></div>;
}

function ClientContract({ row, navigate }: { row: RevenueItem; navigate: (path: string) => void }) {
  const client = row.client_name?.trim() || "Não informado";
  return <div className="min-w-0"><p className="max-w-[230px] truncate font-semibold" title={client}>{client}</p><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="block max-w-[230px] truncate text-xs text-primary" title={row.contract_code ?? undefined}>{row.contract_code ?? "Contrato não informado"}</AppLink></div>;
}

export function RevenuePage({ navigate }: { navigate: (path: string) => void }) {
  const [filters, setFilters] = useState<RevenueFilters>({ page: 1, page_size: PAGE_SIZE, view: "all", sort_by: "operational_relevance", sort_order: "asc" });
  const loader = useCallback(() => getRevenue(filters), [filters]);
  const { state, reload } = useAsyncData(loader);
  const hasFilters = Boolean(filters.search || filters.contract || filters.client || filters.status || filters.due_from || filters.due_to || filters.payment_from || filters.payment_to || filters.quality || (filters.view && filters.view !== "all"));
  const view = collectionView(state.status, state.status === "success" ? state.data.pagination.total : 0, hasFilters);
  const update = (values: Partial<RevenueFilters>) => setFilters((current) => ({ ...current, ...values, page: values.page ?? 1 }));
  const updateSort = (value: string) => {
    const [sort_by, sort_order] = value.split(":") as [string, "asc" | "desc"];
    update({ sort_by, sort_order });
  };

  return <div className="space-y-6">
    <PageHeader eyebrow="Receita · dados operacionais" title="Parcelas e recebimentos" description="Registros reais de ECON_AMORTIZACOES. Recebimentos por período usam a data real da baixa/pagamento, não o vencimento." />
    {state.status === "success" && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><KpiCard compact icon={ReceiptText} label="# Registros" value={String(state.data.summary.total_records)} /><KpiCard compact icon={Landmark} label="Principal Total" value={formatOperationalMoney(state.data.summary.principal_total)} /><KpiCard compact icon={WalletCards} label="Principal Aberto" value={formatOperationalMoney(state.data.summary.principal_open)} /><KpiCard compact icon={Banknote} label="Juros" value={formatOperationalMoney(state.data.summary.interest_amount)} /><KpiCard compact icon={ReceiptText} label="Média PMT" value={formatOperationalMoney(state.data.summary.average_pmt)} /><KpiCard compact icon={AlertTriangle} label="Principal em Atraso" value={formatOperationalMoney(state.data.summary.overdue_principal)} /><KpiCard compact icon={AlertTriangle} label="PMT em Atraso" value={formatOperationalMoney(state.data.summary.overdue_pmt)} /><KpiCard compact icon={AlertTriangle} label="% Inadimplência" value={formatPercentage(state.data.summary.delinquency_percentage)} helper="Regra provisória · PMT vencida ÷ PMT aberta" /></div>}
    <Card className="bg-card/75"><CardContent className="space-y-4 p-4">
      <div className="flex flex-wrap gap-2" aria-label="Filtros rápidos de recebimentos">{QUICK_FILTERS.map((item) => <Button key={item.value} size="sm" variant={(filters.view ?? "all") === item.value ? "default" : "outline"} onClick={() => update({ view: item.value })}>{item.label}</Button>)}</div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><FormField label="Busca"><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value })} placeholder="Contrato, cliente ou parcela" /></div></FormField><FormField label="Contrato"><Input value={filters.contract ?? ""} onChange={(event) => update({ contract: event.target.value })} /></FormField><FormField label="Cliente"><Input value={filters.client ?? ""} onChange={(event) => update({ client: event.target.value })} /></FormField><FormField label="Status"><Input value={filters.status ?? ""} onChange={(event) => update({ status: event.target.value })} /></FormField><FormField label="Qualidade"><Select value={filters.quality ?? ""} onChange={(event) => update({ quality: event.target.value as RevenueFilters["quality"] })}><option value="">Todas</option><option value="VALID">Válida</option><option value="WARNING">Com aviso</option><option value="DIVERGENT">Divergente</option><option value="INVALID">Inválida</option></Select></FormField><FormField label="Ordenar por"><Select value={`${filters.sort_by}:${filters.sort_order}`} onChange={(event) => updateSort(event.target.value)}><option value="operational_relevance:asc">Relevância operacional</option><option value="due_date:asc">Vencimento mais próximo</option><option value="due_date:desc">Vencimento mais distante</option><option value="payment_date:desc">Pagamento mais recente</option><option value="payment_date:asc">Pagamento mais antigo</option></Select></FormField></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><FormField label="Vencimento de"><Input type="date" value={filters.due_from ?? ""} onChange={(event) => update({ due_from: event.target.value })} /></FormField><FormField label="Vencimento até"><Input type="date" value={filters.due_to ?? ""} onChange={(event) => update({ due_to: event.target.value })} /></FormField><FormField label="Baixa real de"><Input type="date" value={filters.payment_from ?? ""} onChange={(event) => update({ payment_from: event.target.value })} /></FormField><FormField label="Baixa real até"><Input type="date" value={filters.payment_to ?? ""} onChange={(event) => update({ payment_to: event.target.value })} /></FormField></div>
    </CardContent></Card>
    {view === "loading" && <LoadingState label="Carregando Receita operacional…" />}
    {view === "error" && <ErrorState message={state.status === "error" ? state.error : undefined} onRetry={reload} />}
    {view === "empty" && <EmptyState title="Nenhum registro de Receita disponível" description="A promoção atual não contém parcelas acessíveis." />}
    {view === "filtered-empty" && <EmptyState title="Nenhum resultado para os filtros" description="Ajuste os filtros para consultar outras parcelas." />}
    {view === "success" && state.status === "success" && <>
      <div className="hidden md:block"><Card className="overflow-hidden bg-card/75"><Table className="min-w-[1120px]"><TableHeader><TableRow><TableHead className="w-[250px]">Cliente / contrato</TableHead><TableHead>Vencimento</TableHead><TableHead>Pagamento</TableHead><TableHead className="text-right">Valor</TableHead><TableHead className="text-right">Principal</TableHead><TableHead className="text-right">Juros</TableHead><TableHead>Situação</TableHead><TableHead>Validação</TableHead><TableHead>Funding / rateio</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/receita/${row.id}`)}><TableCell><ClientContract row={row} navigate={navigate} /></TableCell><TableCell className="whitespace-nowrap">{formatDate(row.due_date)}</TableCell><TableCell className="whitespace-nowrap">{formatDate(row.payment_date)}</TableCell><TableCell className="whitespace-nowrap text-right"><strong>{formatOperationalMoney(row.paid_amount)}</strong><p className="text-xs text-muted-foreground">PMT {formatOperationalMoney(row.expected_amount)}</p></TableCell><TableCell className="whitespace-nowrap text-right tabular-nums">{formatOperationalMoney(row.principal_component)}</TableCell><TableCell className="whitespace-nowrap text-right tabular-nums">{formatOperationalMoney(row.interest_component)}</TableCell><TableCell><RevenueSituation row={row} /></TableCell><TableCell><StatusBadge status={row.bank_validation_status} /></TableCell><TableCell className="space-y-1">{row.funding_status ? <StatusBadge status={row.funding_status} /> : <span className="text-muted-foreground">Sem vínculo</span>}<div><StatusBadge status={row.distribution_status} /></div></TableCell></TableRow>)}</TableBody></Table></Card></div>
      <div className="grid gap-4 md:hidden">{state.data.items.map((row) => <Card key={row.id} className="bg-card/75"><CardContent className="space-y-4 p-4"><div className="flex items-start justify-between gap-3"><ClientContract row={row} navigate={navigate} /><RevenueSituation row={row} /></div><div className="grid grid-cols-2 gap-3 text-sm"><Metric label={Number(row.paid_amount ?? 0) > 0 ? "Valor recebido" : "Valor previsto"} value={formatOperationalMoney(Number(row.paid_amount ?? 0) > 0 ? row.paid_amount : row.expected_amount)} emphasized /><Metric label="Vencimento" value={formatDate(row.due_date)} /><Metric label="Pagamento" value={formatDate(row.payment_date)} /><Metric label="Validação" value={row.bank_validation_status === "NOT_RECORDED" ? "Pendente" : row.bank_validation_status === "VALIDATED" ? "Validada" : "Divergente"} /></div></CardContent></Card>)}</div>
      <Pagination page={state.data.pagination.page} pages={state.data.pagination.pages} total={state.data.pagination.total} onPage={(page) => update({ page })} />
    </>}
  </div>;
}

function Metric({ label, value, emphasized = false }: { label: string; value: string; emphasized?: boolean }) {
  return <div><p className="text-xs text-muted-foreground">{label}</p><p className={emphasized ? "font-semibold tabular-nums" : "font-medium"}>{value}</p></div>;
}

function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} registro(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>;
}
