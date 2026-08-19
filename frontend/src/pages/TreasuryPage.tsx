import { ArrowDownLeft, ArrowUpRight, Banknote, Landmark, Search, TrendingUp, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs, type TabItem } from "@/components/common/Tabs";
import { TreasuryValidationModal } from "@/components/funding/TreasuryValidationModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney } from "@/lib/formatters";
import { treasuryApi } from "@/services/treasuryApi";
import type { TreasuryFilters, TreasuryMovement, TreasuryMovementType } from "@/types/treasuryApi";

export type TreasurySection = "summary" | "flow" | "remunerations" | "reconciliation" | "divergences";
const tabs: TabItem[] = [
  { value: "summary", label: "Visão geral", path: "/tesouraria" },
  { value: "flow", label: "Fluxo consolidado", path: "/tesouraria/fluxo" },
  { value: "remunerations", label: "Remunerações", path: "/tesouraria/remuneracoes" },
  { value: "reconciliation", label: "Conciliação", path: "/tesouraria/conciliacao" },
  { value: "divergences", label: "Divergências", path: "/tesouraria/divergencias" },
];
const typeLabels: Record<TreasuryMovementType, string> = {
  CONTRIBUTION: "Aporte", SALE: "Venda / liberação", REVENUE: "Receita recebida", CAPITAL_REMUNERATION: "Remuneração de capital",
};

export function TreasuryPage({ section = "summary", navigate }: { section?: TreasurySection; navigate: (path: string) => void }) {
  return <div className="space-y-6"><PageHeader eyebrow="Tesouraria · caixa conhecido" title="Fluxo consolidado real" description="Entradas e saídas derivadas dos fatos conhecidos do sistema; não representa saldo bancário conciliado." /><Tabs items={tabs} value={section} navigate={navigate} />
    {section === "summary" || section === "flow" || section === "divergences" ? <RealTreasury key={section} section={section} navigate={navigate} /> : <UnavailableSection section={section} />}
  </div>;
}

function RealTreasury({ section, navigate }: { section: "summary" | "flow" | "divergences"; navigate: (path: string) => void }) {
  const pageSize = section === "flow" ? 100 : 50;
  const [filters, setFilters] = useState<TreasuryFilters>({ page: 1, page_size: pageSize, validation_status: section === "divergences" ? "DIVERGENT" : "" }); const [selected, setSelected] = useState<TreasuryMovement | null>(null);
  const loader = useCallback(async () => {
    const summaryFilters = { period_from: filters.period_from, period_to: filters.period_to, movement_type: filters.movement_type, search: filters.search, investor_id: filters.investor_id, validation_status: filters.validation_status };
    const [summary, movements] = await Promise.all([treasuryApi.getSummary(summaryFilters), treasuryApi.listMovements(filters)]);
    return { summary, movements };
  }, [filters]);
  const { state, reload } = useAsyncData(loader);
  const update = (values: Partial<TreasuryFilters>) => setFilters((current) => ({ ...current, ...values, page: values.page ?? 1 }));
  return <div className="space-y-6"><Card className="bg-card/75"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-6"><FormField label="Período inicial"><Input type="date" value={filters.period_from ?? ""} onChange={(event) => update({ period_from: event.target.value })} /></FormField><FormField label="Período final"><Input type="date" value={filters.period_to ?? ""} onChange={(event) => update({ period_to: event.target.value })} /></FormField><FormField label="Tipo"><Select value={filters.movement_type ?? ""} onChange={(event) => update({ movement_type: event.target.value as TreasuryFilters["movement_type"] })}><option value="">Todos</option><option value="CONTRIBUTION">Aporte</option><option value="SALE">Venda</option><option value="REVENUE">Receita</option></Select></FormField><FormField label="Validação"><Select value={filters.validation_status ?? ""} onChange={(event) => update({ validation_status: event.target.value as TreasuryFilters["validation_status"] })}><option value="">Todas</option><option value="PENDING">Pendente</option><option value="VALIDATED">Validado</option><option value="DIVERGENT">Divergente</option></Select></FormField><FormField label="Contrato, referência ou nome"><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value })} placeholder="Buscar movimento" /></div></FormField><div className="flex items-end"><Button className="w-full" variant="outline" onClick={() => setFilters({ page: 1, page_size: pageSize, validation_status: section === "divergences" ? "DIVERGENT" : "" })}>Limpar filtros</Button></div></CardContent></Card>
    {state.status === "loading" && <LoadingState label="Consolidando caixa real…" />}
    {state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}
    {state.status === "success" && <><SummaryCards summary={state.data.summary} />{state.data.summary.undated_movement_count > 0 || state.data.summary.unknown_amount_count > 0 ? <p className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3 text-sm text-amber-300">Há {state.data.summary.undated_movement_count} Venda(s) sem data financeira e {state.data.summary.unknown_amount_count} movimento(s) sem valor liberado. Eles permanecem explícitos na listagem e não são inventados nos totais.</p> : null}<MovementsTable items={state.data.movements.items} navigate={navigate} onValidate={setSelected} />{state.data.movements.pagination.total > 0 && <Pagination page={state.data.movements.pagination.page} pages={state.data.movements.pagination.pages} total={state.data.movements.pagination.total} onPage={(page) => update({ page })} />}</>}
    <TreasuryValidationModal movement={selected} onClose={() => setSelected(null)} onValidated={reload} />
  </div>;
}

function SummaryCards({ summary }: { summary: Awaited<ReturnType<typeof treasuryApi.getSummary>> }) {
  return <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><KpiCard compact icon={ArrowDownLeft} label="Entradas no período" value={formatMoney(summary.total_inflows)} /><KpiCard compact icon={ArrowUpRight} label="Saídas no período" value={formatMoney(summary.total_outflows)} /><KpiCard compact icon={TrendingUp} label="Fluxo líquido conhecido" value={formatMoney(summary.known_net_flow)} helper="Não representa saldo bancário" /><KpiCard compact icon={Landmark} label="Aportes" value={formatMoney(summary.contributions)} helper={`${summary.contribution_count} movimento(s)`} /><KpiCard compact icon={Banknote} label="Receitas" value={formatMoney(summary.revenues)} helper={`${summary.revenue_count} recebimento(s)`} /><KpiCard compact icon={WalletCards} label="Vendas" value={formatMoney(summary.sales)} helper={`${summary.sale_count} liberação(ões)`} /></div><div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={WalletCards} label="Pendentes de validação" value={String(summary.pending_validation_count)} /><KpiCard compact icon={Landmark} label="Validados" value={String(summary.validated_count)} /><KpiCard compact icon={ArrowUpRight} label="Divergentes" value={String(summary.divergent_count)} helper={`Diferença líquida: ${formatMoney(summary.net_difference_amount)}`} /></div></>;
}

function MovementsTable({ items, navigate, onValidate }: { items: Awaited<ReturnType<typeof treasuryApi.listMovements>>["items"]; navigate: (path: string) => void; onValidate: (movement: TreasuryMovement) => void }) {
  if (items.length === 0) return <EmptyState title="Nenhum movimento de Tesouraria" description="Não há fatos reais correspondentes aos filtros informados." />;
  return <Card className="overflow-hidden bg-card/75"><Table className="min-w-[1280px]"><TableHeader><TableRow><TableHead>Data</TableHead><TableHead>Tipo</TableHead><TableHead>Referência</TableHead><TableHead>Descrição</TableHead><TableHead>Conta / operador</TableHead><TableHead>Entrada</TableHead><TableHead>Saída</TableHead><TableHead>Status</TableHead><TableHead>Validação</TableHead></TableRow></TableHeader><TableBody>{items.map((item) => <TableRow key={item.id} className="cursor-pointer" onClick={() => navigate(item.detail_path)}><TableCell>{item.movement_date ? formatDate(item.movement_date) : <span className="text-amber-300">Data indisponível</span>}</TableCell><TableCell>{typeLabels[item.movement_type]}</TableCell><TableCell><AppLink to={item.detail_path} onNavigate={navigate} className="font-semibold text-primary">{item.reference}</AppLink><p className="text-xs text-muted-foreground">{item.origin}</p></TableCell><TableCell><p className="max-w-[300px]">{item.description}</p>{item.contract_code && <p className="text-xs text-muted-foreground">Contrato {item.contract_code}</p>}</TableCell><TableCell>{item.financial_account ?? item.financial_operator ?? "Não disponível"}</TableCell><TableCell className="font-medium text-emerald-400">{item.inflow === null ? "Valor indisponível" : item.inflow === "0.00" ? "—" : formatMoney(item.inflow)}</TableCell><TableCell className="font-medium text-rose-400">{item.outflow === null ? "Valor indisponível" : item.outflow === "0.00" ? "—" : formatMoney(item.outflow)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell><div className="space-y-2"><StatusBadge status={item.validation_status} /><Button size="sm" variant="outline" disabled={item.amount === null} onClick={(event) => { event.stopPropagation(); onValidate(item); }}>{item.validation_id ? "Corrigir" : "Validar"}</Button></div></TableCell></TableRow>)}</TableBody></Table></Card>;
}

function UnavailableSection({ section }: { section: "remunerations" | "reconciliation" }) {
  const content = section === "remunerations" ? ["Remuneração de Capital aguardando regras", "Nenhum evento de remuneração foi criado nesta fase."] : ["Conciliação bancária automática ainda não implementada", "A validação manual está disponível na listagem; nenhum saldo bancário foi inventado."];
  return <EmptyState title={content[0]} description={content[1]} />;
}

function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} movimento(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>;
}
