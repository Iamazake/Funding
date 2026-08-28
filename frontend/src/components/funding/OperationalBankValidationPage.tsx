import { AlertTriangle, Banknote, CheckCircle2, Clock3, Search, WalletCards } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { TreasuryValidationModal } from "@/components/funding/TreasuryValidationModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney } from "@/lib/formatters";
import { treasuryApi } from "@/services/treasuryApi";
import type { TreasuryFilters, TreasuryMovement } from "@/types/treasuryApi";

const PAGE_SIZE = 25;

type ValidationKind = "SALE" | "REVENUE";

export function OperationalBankValidationPage({
  kind,
  navigate,
}: {
  kind: ValidationKind;
  navigate: (path: string) => void;
}) {
  const isSale = kind === "SALE";
  const [filters, setFilters] = useState<TreasuryFilters>({
    page: 1,
    page_size: PAGE_SIZE,
    movement_type: kind,
    eligible_for_validation: true,
  });
  const [selected, setSelected] = useState<TreasuryMovement | null>(null);
  const loader = useCallback(async () => {
    const summaryFilters: TreasuryFilters = {
      period_from: filters.period_from,
      period_to: filters.period_to,
      movement_type: kind,
      search: filters.search,
      installment: filters.installment,
      validation_status: filters.validation_status,
      eligible_for_validation: true,
    };
    const [summary, movements] = await Promise.all([
      treasuryApi.getSummary(summaryFilters),
      treasuryApi.listMovements(filters),
    ]);
    return { summary, movements };
  }, [filters, kind]);
  const { state, reload } = useAsyncData(loader);

  const update = (values: Partial<TreasuryFilters>) =>
    setFilters((current) => ({ ...current, ...values, movement_type: kind, eligible_for_validation: true, page: values.page ?? 1 }));
  const clear = () => setFilters({ page: 1, page_size: PAGE_SIZE, movement_type: kind, eligible_for_validation: true });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={isSale ? "Vendas · dados operacionais" : "Receita · recebimentos operacionais"}
        title="Validação bancária"
        description={
          isSale
            ? "Saídas reais por liberação, compartilhadas com a Tesouraria."
            : "Entradas reais de parcelas pagas, compartilhadas com a Tesouraria."
        }
      />
      <Filters kind={kind} filters={filters} update={update} clear={clear} />

      {state.status === "loading" && <LoadingState label="Carregando validações bancárias reais…" />}
      {state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}
      {state.status === "success" && (
        <>
          <Summary kind={kind} summary={state.data.summary} />
          <ValidationTable
            kind={kind}
            items={state.data.movements.items}
            navigate={navigate}
            onValidate={setSelected}
          />
          {state.data.movements.pagination.total > 0 && (
            <Pagination
              page={state.data.movements.pagination.page}
              pages={state.data.movements.pagination.pages}
              total={state.data.movements.pagination.total}
              onPage={(page) => update({ page })}
            />
          )}
        </>
      )}

      <TreasuryValidationModal movement={selected} onClose={() => setSelected(null)} onValidated={reload} />
    </div>
  );
}

function Filters({
  kind,
  filters,
  update,
  clear,
}: {
  kind: ValidationKind;
  filters: TreasuryFilters;
  update: (values: Partial<TreasuryFilters>) => void;
  clear: () => void;
}) {
  return (
    <Card className="bg-card/75">
      <CardContent className={`grid gap-3 p-4 sm:grid-cols-2 ${kind === "REVENUE" ? "xl:grid-cols-6" : "xl:grid-cols-5"}`}>
        <FormField label="Período inicial">
          <Input type="date" value={filters.period_from ?? ""} onChange={(event) => update({ period_from: event.target.value })} />
        </FormField>
        <FormField label="Período final">
          <Input type="date" value={filters.period_to ?? ""} onChange={(event) => update({ period_to: event.target.value })} />
        </FormField>
        <FormField label="Contrato ou cliente">
          <div className="relative">
            <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
            <Input className="pl-9" value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value })} placeholder="Buscar" />
          </div>
        </FormField>
        {kind === "REVENUE" && (
          <FormField label="Parcela">
            <Input value={filters.installment ?? ""} onChange={(event) => update({ installment: event.target.value })} placeholder="Número ou código" />
          </FormField>
        )}
        <FormField label="Validação">
          <Select value={filters.validation_status ?? ""} onChange={(event) => update({ validation_status: event.target.value as TreasuryFilters["validation_status"] })}>
            <option value="">Todas</option>
            <option value="PENDING">Pendente</option>
            <option value="VALIDATED">Validada</option>
            <option value="DIVERGENT">Divergente</option>
          </Select>
        </FormField>
        <div className="flex items-end"><Button className="w-full" variant="outline" onClick={clear}>Limpar filtros</Button></div>
      </CardContent>
    </Card>
  );
}

function Summary({ kind, summary }: { kind: ValidationKind; summary: Awaited<ReturnType<typeof treasuryApi.getSummary>> }) {
  const total = kind === "SALE" ? summary.sale_count : summary.revenue_count;
  const amount = kind === "SALE" ? summary.sales : summary.revenues;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard compact icon={kind === "SALE" ? WalletCards : Banknote} label={kind === "SALE" ? "Total" : "Recebimentos"} value={String(total)} helper={formatMoney(amount)} />
      <KpiCard compact icon={Clock3} label="Pendentes" value={String(summary.pending_validation_count)} />
      <KpiCard compact icon={CheckCircle2} label="Validadas" value={String(summary.validated_count)} />
      <KpiCard compact icon={AlertTriangle} label="Divergentes" value={String(summary.divergent_count)} />
    </div>
  );
}

function ValidationTable({
  kind,
  items,
  navigate,
  onValidate,
}: {
  kind: ValidationKind;
  items: TreasuryMovement[];
  navigate: (path: string) => void;
  onValidate: (movement: TreasuryMovement) => void;
}) {
  if (items.length === 0) {
    return <EmptyState title="Nenhum registro encontrado" description="Não há fatos operacionais reais correspondentes aos filtros informados." />;
  }
  return kind === "SALE" ? (
    <Card className="overflow-hidden bg-card/75">
      <Table className="min-w-[1140px]">
        <TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Tipo</TableHead><TableHead>Data</TableHead><TableHead>Valor liberado</TableHead><TableHead>Funding</TableHead><TableHead>Qualidade</TableHead><TableHead>Validação</TableHead><TableHead>Ação</TableHead></TableRow></TableHeader>
        <TableBody>{items.map((item) => (
          <TableRow key={item.id}>
            <TableCell><AppLink to={item.detail_path} onNavigate={navigate} className="font-semibold text-primary">{item.contract_code ?? item.reference}</AppLink><p className="text-xs text-muted-foreground">{item.client_name ?? "Não informado"}</p></TableCell>
            <TableCell><OperationTypeBadge item={item} /></TableCell>
            <TableCell>{item.movement_date ? formatDate(item.movement_date) : "Não informado"}</TableCell>
            <TableCell className="font-medium">{item.amount ? formatMoney(item.amount) : "Não informado"}</TableCell>
            <TableCell>{item.funding_status === "NOT_INFORMED" || !item.funding_status ? <span className="text-muted-foreground">Não informado</span> : <StatusBadge status={item.funding_status} />}</TableCell>
            <TableCell>{item.data_quality_status ? <StatusBadge status={item.data_quality_status} /> : "Não informado"}</TableCell>
            <TableCell><StatusBadge status={item.validation_status} /></TableCell>
            <TableCell><ValidationAction item={item} onValidate={onValidate} /></TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
    </Card>
  ) : (
    <Card className="overflow-hidden bg-card/75">
      <Table className="min-w-[980px]">
        <TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Tipo</TableHead><TableHead>Parcela</TableHead><TableHead>Pagamento</TableHead><TableHead>Valor recebido</TableHead><TableHead>Diferença</TableHead><TableHead>Validação</TableHead><TableHead>Ação</TableHead></TableRow></TableHeader>
        <TableBody>{items.map((item) => (
          <TableRow key={item.id}>
            <TableCell><AppLink to={item.detail_path} onNavigate={navigate} className="font-semibold text-primary">{item.contract_code ?? item.reference}</AppLink><p className="text-xs text-muted-foreground">{item.client_name ?? "Não informado"}</p></TableCell>
            <TableCell><OperationTypeBadge item={item} /></TableCell>
            <TableCell>{item.installment_code ?? "Não informado"}</TableCell>
            <TableCell>{item.movement_date ? formatDate(item.movement_date) : "Não informado"}</TableCell>
            <TableCell className="font-medium text-emerald-400">{formatMoney(item.amount ?? "0.00")}</TableCell>
            <TableCell>{item.difference_amount === null ? "—" : formatMoney(item.difference_amount)}</TableCell>
            <TableCell><StatusBadge status={item.validation_status} /></TableCell>
            <TableCell><ValidationAction item={item} onValidate={onValidate} /></TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
    </Card>
  );
}

function OperationTypeBadge({ item }: { item: TreasuryMovement }) {
  const label = item.continuity_type === "REFINANCING"
    ? "REFIN"
    : item.continuity_type === "RENEGOTIATION" || item.continuity_type === "ROLLOVER"
      ? "RENEG"
      : "NORMAL";
  return <StatusBadge status={label} />;
}

function ValidationAction({ item, onValidate }: { item: TreasuryMovement; onValidate: (movement: TreasuryMovement) => void }) {
  const eligible = item.amount !== null && Number(item.amount) > 0;
  return <Button size="sm" variant="outline" disabled={!eligible} onClick={() => onValidate(item)}>{item.validation_id ? "Ver / corrigir" : "Validar"}</Button>;
}

function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground"><span>{total} registro(s) · página {page} de {Math.max(pages, 1)}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</Button><Button variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Próxima</Button></div></div>;
}
