import { AlertTriangle, ArrowLeft, Banknote, Landmark, Search, WalletCards } from "lucide-react";
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
import { formatOperationalMoney, formatRate } from "@/lib/operationalFormat";
import { collectionView, getSale, getSales } from "@/services/operationalApi";
import type { QualityMessage, SaleItem, SalesFilters } from "@/types/operational";

const PAGE_SIZE = 25;

function QualityIndicator({ row }: { row: SaleItem }) {
  if (row.divergence_count > 0) return <span className="font-medium text-rose-400">{row.divergence_count} divergência(s)</span>;
  if (row.warning_count > 0) return <span className="text-amber-400">{row.warning_count} aviso(s)</span>;
  return <span className="text-muted-foreground">Sem avisos</span>;
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
      <Card className="overflow-hidden bg-card/75"><Table className="min-w-[1400px]"><TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Operação</TableHead><TableHead>Liberação</TableHead><TableHead>Prazo</TableHead><TableHead>Principal</TableHead><TableHead>IOF</TableHead><TableHead>Financiado</TableHead><TableHead>PMT</TableHead><TableHead>Liberado</TableHead><TableHead>Taxa</TableHead><TableHead>Status</TableHead><TableHead>Qualidade</TableHead><TableHead>Funding</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${row.id}`)}><TableCell><AppLink to={`/vendas/${row.id}`} onNavigate={navigate} className="font-semibold text-primary">{row.contract_code ?? "Contrato não informado"}</AppLink><p className="text-xs text-muted-foreground">{row.client_name ?? `Cliente não resolvido · ${row.source_client_code ?? "sem código"}`}</p></TableCell><TableCell>{formatDate(row.operation_date)}</TableCell><TableCell>{formatDate(row.release_date)}</TableCell><TableCell>{row.term ?? "—"}</TableCell><TableCell>{formatOperationalMoney(row.principal)}</TableCell><TableCell>{formatOperationalMoney(row.iof)}</TableCell><TableCell>{formatOperationalMoney(row.financed_amount)}</TableCell><TableCell>{formatOperationalMoney(row.installment_amount)}</TableCell><TableCell>{formatOperationalMoney(row.released_amount)}</TableCell><TableCell>{formatRate(row.interest_rate)}</TableCell><TableCell><StatusBadge status={row.status ?? "NÃO INFORMADO"} /></TableCell><TableCell><QualityIndicator row={row} /></TableCell><TableCell>Não informado</TableCell></TableRow>)}</TableBody></Table></Card>
      <Pagination page={state.data.pagination.page} pages={state.data.pagination.pages} total={state.data.pagination.total} onPage={(page) => update({ page })} />
    </>}
  </div>;
}

export function SalesDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(() => getSale(id), [id]);
  const { state, reload } = useAsyncData(loader);
  if (state.status === "loading") return <LoadingState label="Carregando venda operacional…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const row = state.data;
  return <div className="space-y-6"><AppLink to="/vendas" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Vendas</AppLink><PageHeader eyebrow="Venda operacional" title={row.contract_code ?? "Contrato não informado"} description={row.client_name ?? "Cliente não resolvido na promoção atual."} actions={<StatusBadge status={row.data_quality_status} />} /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Landmark} label="Principal" value={formatOperationalMoney(row.principal)} /><KpiCard compact icon={Banknote} label="Valor liberado" value={formatOperationalMoney(row.released_amount)} /><KpiCard compact icon={WalletCards} label="PMT" value={formatOperationalMoney(row.installment_amount)} /><KpiCard compact icon={AlertTriangle} label="Avisos / divergências" value={`${row.warning_count} / ${row.divergence_count}`} /></div><InfoGrid rows={[["Código do cliente", row.source_client_code ?? "Não informado"], ["Data da operação", formatDate(row.operation_date)], ["Data de liberação", formatDate(row.release_date)], ["Primeiro vencimento", formatDate(row.first_due_date)], ["Prazo", row.term ? `${row.term} meses` : "Não informado"], ["IOF", formatOperationalMoney(row.iof)], ["Valor financiado", formatOperationalMoney(row.financed_amount)], ["Taxa de juros", formatRate(row.interest_rate)], ["TIR", formatRate(row.irr_rate)], ["CET mensal", formatRate(row.cet_monthly_rate)], ["Status", row.status ?? "Não informado"], ["Validação bancária", "Pendente / não registrada"], ["Composição do funding", "Não informada"], ["Investidores", "Não informados"], ["Capital REMO", "Não informado"]]} /><QualityPanel warnings={row.warnings} divergences={row.divergences} /></div>;
}

export function SalesDivergencesPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(() => getSales({ page: 1, page_size: 100, quality: "DIVERGENT" }), []);
  const { state, reload } = useAsyncData(loader);
  return <div className="space-y-6"><PageHeader eyebrow="Vendas" title="Divergências operacionais" description="Empréstimos sem contrato e outras divergências reais da promoção atual." />{state.status === "loading" ? <LoadingState /> : state.status === "error" ? <ErrorState message={state.error} onRetry={reload} /> : state.data.items.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato</TableHead><TableHead>Cliente</TableHead><TableHead>Status</TableHead><TableHead>Motivos</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${row.id}`)}><TableCell>{row.contract_code ?? "Não informado"}</TableCell><TableCell>{row.client_name ?? "Não resolvido"}</TableCell><TableCell><StatusBadge status={row.data_quality_status} /></TableCell><TableCell>{row.divergence_count} divergência(s)</TableCell></TableRow>)}</TableBody></Table></Card>}</div>;
}

export function SalesBankValidationPage({ navigate }: { navigate: (path: string) => void }) {
  return <div className="space-y-6"><AppLink to="/vendas" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Vendas</AppLink><PageHeader eyebrow="Vendas" title="Validação bancária" description="Nenhuma validação bancária real foi integrada nesta fase." /><EmptyState title="Pendente / não registrada" description="Os contratos reais não foram associados a movimentos bancários ou contas fictícias." /></div>;
}

function QualityPanel({ warnings, divergences }: { warnings: QualityMessage[]; divergences: QualityMessage[] }) {
  return <div className="grid gap-4 lg:grid-cols-2"><Card className="bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-amber-400">Avisos ({warnings.length})</h2><div className="mt-3 space-y-2 text-sm">{warnings.length ? warnings.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhum aviso.</p>}</div></CardContent></Card><Card className="border-rose-400/30 bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-rose-400">Divergências ({divergences.length})</h2><div className="mt-3 space-y-2 text-sm">{divergences.length ? divergences.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhuma divergência.</p>}</div></CardContent></Card></div>;
}

function InfoGrid({ rows }: { rows: [string, string][] }) {
  return <Card className="bg-card/75"><CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label}><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</CardContent></Card>;
}

function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} registro(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>;
}
