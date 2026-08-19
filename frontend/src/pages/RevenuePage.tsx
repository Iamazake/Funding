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
import { formatDate } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import { collectionView, getRevenue } from "@/services/operationalApi";
import type { RevenueFilters, RevenueItem } from "@/types/operational";

const PAGE_SIZE = 25;

function QualityIndicator({ row }: { row: RevenueItem }) {
  if (row.divergence_count > 0) return <span className="font-semibold text-rose-400">{row.divergence_count} divergência(s)</span>;
  if (row.warning_count > 0) return <span className="text-amber-400">{row.warning_count} aviso(s)</span>;
  return <span className="text-muted-foreground">Sem avisos</span>;
}

export function RevenuePage({ navigate }: { navigate: (path: string) => void }) {
  const [filters, setFilters] = useState<RevenueFilters>({ page: 1, page_size: PAGE_SIZE, sort_by: "due_date", sort_order: "desc" });
  const loader = useCallback(() => getRevenue(filters), [filters]);
  const { state, reload } = useAsyncData(loader);
  const hasFilters = Boolean(filters.search || filters.contract || filters.client || filters.status || filters.due_from || filters.due_to || filters.payment_from || filters.payment_to || filters.quality);
  const view = collectionView(state.status, state.status === "success" ? state.data.pagination.total : 0, hasFilters);
  const update = (values: Partial<RevenueFilters>) => setFilters((current) => ({ ...current, ...values, page: values.page ?? 1 }));

  return <div className="space-y-6">
    <PageHeader eyebrow="Receita · dados operacionais" title="Parcelas e recebimentos" description="Registros reais de ECON_AMORTIZACOES. Recebimentos por período usam a data real da baixa/pagamento, não o vencimento." />
    {state.status === "success" && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><KpiCard compact icon={ReceiptText} label="Registros" value={String(state.data.summary.total_records)} /><KpiCard compact icon={WalletCards} label="Valor esperado" value={formatOperationalMoney(state.data.summary.expected_amount)} /><KpiCard compact icon={Banknote} label="Valor pago" value={formatOperationalMoney(state.data.summary.paid_amount)} /><KpiCard compact icon={Landmark} label="Principal" value={formatOperationalMoney(state.data.summary.principal_received)} /><KpiCard compact icon={AlertTriangle} label="Divergências" value={String(state.data.summary.divergent_records)} /></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={ReceiptText} label="Juros" value={formatOperationalMoney(state.data.summary.interest_amount)} /><KpiCard compact icon={AlertTriangle} label="Descontos" value={formatOperationalMoney(state.data.summary.discount_amount)} /><KpiCard compact icon={WalletCards} label="Pendentes" value={String(state.data.summary.pending_records)} /><KpiCard compact icon={AlertTriangle} label="Com warning" value={String(state.data.summary.warning_records)} /></div></>}
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-9"><FormField label="Busca"><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value })} placeholder="Contrato, cliente ou parcela" /></div></FormField><FormField label="Contrato"><Input value={filters.contract ?? ""} onChange={(event) => update({ contract: event.target.value })} /></FormField><FormField label="Cliente"><Input value={filters.client ?? ""} onChange={(event) => update({ client: event.target.value })} /></FormField><FormField label="Status"><Input value={filters.status ?? ""} onChange={(event) => update({ status: event.target.value })} /></FormField><FormField label="Vencimento de"><Input type="date" value={filters.due_from ?? ""} onChange={(event) => update({ due_from: event.target.value })} /></FormField><FormField label="Vencimento até"><Input type="date" value={filters.due_to ?? ""} onChange={(event) => update({ due_to: event.target.value })} /></FormField><FormField label="Baixa real de"><Input type="date" value={filters.payment_from ?? ""} onChange={(event) => update({ payment_from: event.target.value })} /></FormField><FormField label="Baixa real até"><Input type="date" value={filters.payment_to ?? ""} onChange={(event) => update({ payment_to: event.target.value })} /></FormField><FormField label="Qualidade"><Select value={filters.quality ?? ""} onChange={(event) => update({ quality: event.target.value as RevenueFilters["quality"] })}><option value="">Todas</option><option value="VALID">Válida</option><option value="WARNING">Com aviso</option><option value="DIVERGENT">Divergente</option><option value="INVALID">Inválida</option></Select></FormField></CardContent></Card>
    {view === "loading" && <LoadingState label="Carregando Receita operacional…" />}
    {view === "error" && <ErrorState message={state.status === "error" ? state.error : undefined} onRetry={reload} />}
    {view === "empty" && <EmptyState title="Nenhum registro de Receita disponível" description="A promoção atual não contém parcelas acessíveis." />}
    {view === "filtered-empty" && <EmptyState title="Nenhum resultado para os filtros" description="Ajuste os filtros para consultar outras parcelas." />}
    {view === "success" && state.status === "success" && <><div className="hidden md:block"><Card className="overflow-hidden bg-card/75"><Table className="min-w-[1700px]"><TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Parcela</TableHead><TableHead>Vencimento</TableHead><TableHead>Pagamento</TableHead><TableHead>PMT</TableHead><TableHead>Pago</TableHead><TableHead>Principal</TableHead><TableHead>Juros</TableHead><TableHead>Desconto</TableHead><TableHead>Situação</TableHead><TableHead>Qualidade</TableHead><TableHead>Fonte principal</TableHead><TableHead>Funding</TableHead><TableHead>Rateio</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/receita/${row.id}`)}><TableCell><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="font-semibold text-primary">{row.contract_code ?? "Contrato não informado"}</AppLink><p className="text-xs text-muted-foreground">{row.client_name ?? "Cliente não resolvido"}</p></TableCell><TableCell>{row.installment_code ?? "—"}</TableCell><TableCell>{formatDate(row.due_date)}</TableCell><TableCell>{formatDate(row.payment_date)}</TableCell><TableCell>{formatOperationalMoney(row.expected_amount)}</TableCell><TableCell>{formatOperationalMoney(row.paid_amount)}</TableCell><TableCell>{formatOperationalMoney(row.principal_component)}</TableCell><TableCell>{formatOperationalMoney(row.interest_component)}</TableCell><TableCell>{formatOperationalMoney(row.discount_amount)}</TableCell><TableCell><StatusBadge status={row.situation ?? row.installment_status ?? "NÃO INFORMADA"} /></TableCell><TableCell><QualityIndicator row={row} /></TableCell><TableCell>{row.primary_source_name ?? "Não identificada"}</TableCell><TableCell>{row.funding_status ? <StatusBadge status={row.funding_status} /> : "Sem vínculo"}</TableCell><TableCell><StatusBadge status={row.distribution_status} /></TableCell></TableRow>)}</TableBody></Table></Card></div><div className="grid gap-4 md:hidden">{state.data.items.map((row) => <Card key={row.id} className="bg-card/75"><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="font-semibold text-primary">{row.contract_code ?? "Contrato não informado"}</AppLink><p className="text-xs text-muted-foreground">Parcela {row.installment_code ?? "—"} · {row.client_name ?? "Cliente não resolvido"}</p></div><StatusBadge status={row.distribution_status} /></div><div className="grid grid-cols-3 gap-2 text-sm"><Metric label="Pago" value={formatOperationalMoney(row.paid_amount)} /><Metric label="Principal" value={formatOperationalMoney(row.principal_component)} /><Metric label="Juros" value={formatOperationalMoney(row.interest_component)} /></div><p className="text-xs text-muted-foreground">Fonte principal: {row.primary_source_name ?? "não identificada"}</p></CardContent></Card>)}</div><Pagination page={state.data.pagination.page} pages={state.data.pagination.pages} total={state.data.pagination.total} onPage={(page) => update({ page })} /></>}
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs text-muted-foreground">{label}</p><p className="font-medium">{value}</p></div>;
}

function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} registro(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>;
}
