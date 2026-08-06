import { AlertTriangle, Banknote, CheckCircle2, Columns3, Download, Landmark, ReceiptText, Scale, WalletCards } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { AppLink } from "@/components/app/AppLink";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { requiredRevenueColumns, revenueColumnLabels, revenueStatusLabels } from "@/data/revenueOptions";
import { formatCentsAmount, formatDate } from "@/lib/formatters";
import { cents, sumCents } from "@/repositories/fundingRepository";
import { fundingRepository, useFundingState, useRevenueRecords } from "@/services/fundingService";
import type { ContractFundingAllocation, RevenueColumnKey, RevenueRecordView } from "@/types/funding";

function allocationsForRecord(state: ReturnType<typeof useFundingState>, row: RevenueRecordView): ContractFundingAllocation[] {
  const receipt = state.treasuryIncomingReceipts.find((item) => item.id === row.id);
  if (!receipt?.fundingContractId) return [];
  const date = row.operationalPaymentDate ?? row.dueDate;
  return state.contractFundingAllocations.filter((item) => item.fundingContractId === receipt.fundingContractId
    && item.validFrom.slice(0, 10) <= date && (!item.validUntil || date < item.validUntil.slice(0, 10)));
}

function absMoney(value: string): bigint { const parsed = cents(value); return parsed < 0n ? -parsed : parsed; }

export function RevenuePage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState(); const records = useRevenueRecords();
  const [from, setFrom] = useState("2026-07-01"); const [to, setTo] = useState("2026-08-31"); const [competence, setCompetence] = useState("");
  const [contract, setContract] = useState(""); const [client, setClient] = useState(""); const [installment, setInstallment] = useState("");
  const [operationalStatus, setOperationalStatus] = useState(""); const [revenueStatus, setRevenueStatus] = useState(""); const [bankStatus, setBankStatus] = useState("");
  const [reconciliation, setReconciliation] = useState(""); const [operator, setOperator] = useState(""); const [investor, setInvestor] = useState("");
  const [contribution, setContribution] = useState(""); const [source, setSource] = useState(""); const [onlyDivergent, setOnlyDivergent] = useState(false);
  const [onlyDiscount, setOnlyDiscount] = useState(false); const [onlyLoss, setOnlyLoss] = useState(false); const [onlyUnallocated, setOnlyUnallocated] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const preferences = state.revenueColumnPreferences;

  const rows = useMemo(() => records.filter((row) => {
    const date = row.operationalPaymentDate ?? row.dueDate; const allocations = allocationsForRecord(state, row);
    const allocationSourceIds = allocations.map((item) => item.fundingSourceId); const allocationInvestorIds = allocations.map((item) => item.investorId); const allocationContributionIds = allocations.map((item) => item.contributionId);
    return (!from || date >= from) && (!to || date <= to) && (!competence || row.paymentReference.competence === competence)
      && (!contract || row.contractCode.toLowerCase().includes(contract.toLowerCase())) && (!client || row.maskedClientName.toLowerCase().includes(client.toLowerCase()))
      && (!installment || String(row.installmentNumber) === installment) && (!operationalStatus || row.operationalStatus === operationalStatus)
      && (!revenueStatus || row.revenueStatus === revenueStatus) && (!bankStatus || row.bankValidationStatus === bankStatus)
      && (!reconciliation || row.reconciliationStatus === reconciliation) && (!operator || row.financialOperator.toLowerCase().includes(operator.toLowerCase()))
      && (!investor || allocationInvestorIds.includes(investor)) && (!contribution || allocationContributionIds.includes(contribution)) && (!source || allocationSourceIds.includes(source))
      && (!onlyDivergent || ["COMPONENT_DIVERGENCE", "BANK_DIVERGENCE", "PARTIALLY_VALIDATED"].includes(row.revenueStatus))
      && (!onlyDiscount || cents(row.discountAmount) > 0n) && (!onlyLoss || cents(row.lossAmount) > 0n)
      && (!onlyUnallocated || ["NOT_CALCULATED", "DIVERGENT", "REVIEW_REQUIRED"].includes(row.allocationStatus));
  }), [bankStatus, client, competence, contract, contribution, from, installment, investor, onlyDiscount, onlyDivergent, onlyLoss, onlyUnallocated, operationalStatus, operator, reconciliation, records, revenueStatus, source, state, to]);

  const total = (selector: (row: RevenueRecordView) => string) => sumCents(rows.map(selector));
  const bankCash = sumCents(state.treasuryEntries.filter((item) => item.type === "PMT_RECEIVED" && item.direction === "ENTRADA" && item.status === "CONFIRMADO" && rows.some((row) => row.id === item.incomingReceiptId)).map((item) => item.amount));
  const componentDifference = rows.reduce((sum, row) => sum + absMoney(row.componentDifference), 0n).toString();
  const toggleColumn = (column: RevenueColumnKey) => {
    if (requiredRevenueColumns.includes(column)) return;
    const visible = preferences.visibleColumns.includes(column) ? preferences.visibleColumns.filter((item) => item !== column) : [...preferences.visibleColumns, column];
    fundingRepository.updateRevenueColumnPreferences({ ...preferences, visibleColumns: visible });
  };
  return <div className="space-y-6">
    <PageHeader eyebrow="Receita" title="Recebimentos" description="Visão analítica das parcelas e componentes do mesmo recebimento usado pela Tesouraria, sem duplicar caixa." actions={<><Button variant="outline" onClick={() => setColumnsOpen(true)}><Columns3 className="size-4" />Colunas</Button><Button variant="outline" onClick={() => exportRevenue(rows)}><Download className="size-4" />Exportar visão demo</Button></>} />

    <section className="space-y-3"><h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Entrada total e composição</h2><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><KpiCard compact icon={Banknote} label="Caixa confirmado" value={formatCentsAmount(bankCash)} helper="Uma entrada total por movimento" /><KpiCard compact icon={ReceiptText} label="Total previsto" value={formatCentsAmount(total((row) => row.expectedInstallmentAmount))} /><KpiCard compact icon={WalletCards} label="Total pago operacional" value={formatCentsAmount(total((row) => row.paidAmount))} /><KpiCard compact icon={Scale} label="Total apurado" value={formatCentsAmount(total((row) => row.apuratedAmount))} /><KpiCard compact icon={AlertTriangle} label="Diferença dos componentes" value={formatCentsAmount(componentDifference)} /></div></section>
    <section className="space-y-3"><h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Recuperação, receita financeira, tributos e reduções</h2><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><KpiCard compact icon={Landmark} label="Principal recuperado" value={formatCentsAmount(total((row) => row.principalAmount))} /><KpiCard compact icon={ReceiptText} label="Juros recebidos" value={formatCentsAmount(total((row) => row.interestAmount))} /><KpiCard compact icon={Landmark} label="IOF" value={formatCentsAmount(total((row) => row.iofAmount))} helper="Não atribuído automaticamente" /><KpiCard compact icon={ReceiptText} label="Multas" value={formatCentsAmount(total((row) => row.penaltyAmount))} /><KpiCard compact icon={AlertTriangle} label="Descontos" value={formatCentsAmount(total((row) => row.discountAmount))} /><KpiCard compact icon={AlertTriangle} label="Prejuízos" value={formatCentsAmount(total((row) => row.lossAmount))} /><KpiCard compact icon={CheckCircle2} label="Aguardando validação" value={String(rows.filter((row) => row.revenueStatus === "PENDING_BANK_VALIDATION").length)} /><KpiCard compact icon={CheckCircle2} label="Recebimentos validados" value={String(rows.filter((row) => row.revenueStatus === "VALIDATED").length)} /><KpiCard compact icon={AlertTriangle} label="Recebimentos divergentes" value={String(rows.filter((row) => ["COMPONENT_DIVERGENCE", "BANK_DIVERGENCE", "PARTIALLY_VALIDATED"].includes(row.revenueStatus)).length)} /><KpiCard compact icon={AlertTriangle} label="Movimentos não encontrados" value={String(rows.filter((row) => row.bankValidationStatus === "MOVEMENT_NOT_FOUND").length)} /></div></section>

    <RevenueFilters state={state} values={{ from, to, competence, contract, client, installment, operationalStatus, revenueStatus, bankStatus, reconciliation, operator, investor, contribution, source, onlyDivergent, onlyDiscount, onlyLoss, onlyUnallocated }} setters={{ setFrom, setTo, setCompetence, setContract, setClient, setInstallment, setOperationalStatus, setRevenueStatus, setBankStatus, setReconciliation, setOperator, setInvestor, setContribution, setSource, setOnlyDivergent, setOnlyDiscount, setOnlyLoss, setOnlyUnallocated }} />

    <div className="hidden md:block"><Card className="overflow-hidden bg-card/75"><Table className="min-w-[1500px]"><TableHeader className="sticky top-0 z-20 bg-card"><TableRow>{preferences.visibleColumns.map((column) => <TableHead key={column} className={column === "contract" ? "sticky left-0 z-30 min-w-64 bg-card" : "whitespace-nowrap"}>{revenueColumnLabels[column]}</TableHead>)}</TableRow></TableHeader><TableBody>{rows.map((row) => <RevenueTableRow key={row.id} row={row} state={state} navigate={navigate} columns={preferences.visibleColumns} compact={preferences.density === "COMPACT"} />)}</TableBody></Table></Card></div>
    <div className="grid gap-4 md:hidden">{rows.map((row) => <Card key={row.id} className="bg-card/75"><CardContent className="space-y-3 p-4"><div className="flex items-start justify-between gap-3"><div><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="font-semibold text-primary">{row.contractCode}</AppLink><p className="text-xs text-muted-foreground">Parcela {row.installmentNumber}/{row.totalInstallments} · {row.maskedClientName}</p></div><StatusBadge status={row.revenueStatus} /></div><div className="grid grid-cols-3 gap-2 text-sm"><Metric label="Pago" value={formatCentsAmount(row.paidAmount)} /><Metric label="Principal" value={formatCentsAmount(row.principalAmount)} /><Metric label="Juros" value={formatCentsAmount(row.interestAmount)} /></div></CardContent></Card>)}</div>

    <Modal open={columnsOpen} title="Colunas e densidade" description="A preferência fica no repositório demonstrativo, sem acesso direto da página ao localStorage." onClose={() => setColumnsOpen(false)} footer={<Button onClick={() => setColumnsOpen(false)}>Concluir</Button>}><div className="grid gap-3 sm:grid-cols-2">{(Object.keys(revenueColumnLabels) as RevenueColumnKey[]).map((column) => <label key={column} className="flex items-center gap-2 rounded-lg border p-3 text-sm"><input type="checkbox" checked={preferences.visibleColumns.includes(column)} disabled={requiredRevenueColumns.includes(column)} onChange={() => toggleColumn(column)} />{revenueColumnLabels[column]}</label>)}</div><div className="mt-5"><FormField label="Densidade"><Select value={preferences.density} onChange={(event) => fundingRepository.updateRevenueColumnPreferences({ ...preferences, density: event.target.value as "COMPACT" | "COMFORTABLE" })}><option value="COMPACT">Compacta</option><option value="COMFORTABLE">Confortável</option></Select></FormField></div></Modal>
  </div>;
}

type FilterValues = { from: string; to: string; competence: string; contract: string; client: string; installment: string; operationalStatus: string; revenueStatus: string; bankStatus: string; reconciliation: string; operator: string; investor: string; contribution: string; source: string; onlyDivergent: boolean; onlyDiscount: boolean; onlyLoss: boolean; onlyUnallocated: boolean };
type FilterSetters = { [K in keyof FilterValues as `set${Capitalize<K>}`]: (value: FilterValues[K]) => void };

function RevenueFilters({ state, values, setters }: { state: ReturnType<typeof useFundingState>; values: FilterValues; setters: FilterSetters }) {
  return <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Filtros da Receita</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><FormField label="De"><Input type="date" value={values.from} onChange={(event) => setters.setFrom(event.target.value)} /></FormField><FormField label="Até"><Input type="date" value={values.to} onChange={(event) => setters.setTo(event.target.value)} /></FormField><FormField label="Competência"><Input type="month" value={values.competence} onChange={(event) => setters.setCompetence(event.target.value)} /></FormField><FormField label="Contrato"><Input value={values.contract} onChange={(event) => setters.setContract(event.target.value)} /></FormField><FormField label="Cliente mascarado"><Input value={values.client} onChange={(event) => setters.setClient(event.target.value)} /></FormField><FormField label="Parcela"><Input inputMode="numeric" value={values.installment} onChange={(event) => setters.setInstallment(event.target.value.replace(/\D/g, ""))} /></FormField><FormField label="Status operacional"><Select value={values.operationalStatus} onChange={(event) => setters.setOperationalStatus(event.target.value)}><option value="">Todos</option><option value="WAITING_WRITE_OFF">Aguardando baixa</option><option value="WRITTEN_OFF">Baixada</option><option value="REVERSED">Estornada</option><option value="CANCELLED">Cancelada</option></Select></FormField><FormField label="Status da Receita"><Select value={values.revenueStatus} onChange={(event) => setters.setRevenueStatus(event.target.value)}><option value="">Todos</option>{Object.entries(revenueStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></FormField><FormField label="Validação bancária"><Select value={values.bankStatus} onChange={(event) => setters.setBankStatus(event.target.value)}><option value="">Todas</option><option value="PENDING">Pendente</option><option value="VALUE_MISMATCH">Valor divergente</option><option value="MOVEMENT_NOT_FOUND">Não encontrado</option><option value="VALIDATED">Validada</option></Select></FormField><FormField label="Conciliação"><Select value={values.reconciliation} onChange={(event) => setters.setReconciliation(event.target.value)}><option value="">Todas</option><option value="PENDING">Pendente</option><option value="PARTIAL">Parcial</option><option value="RECONCILED">Conciliada</option><option value="DIVERGENT">Divergente</option><option value="REVERSED">Estornada</option></Select></FormField><FormField label="Operador financeiro"><Input value={values.operator} onChange={(event) => setters.setOperator(event.target.value)} /></FormField><FormField label="Investidor"><Select value={values.investor} onChange={(event) => setters.setInvestor(event.target.value)}><option value="">Todos</option>{state.investors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></FormField><FormField label="Aporte"><Select value={values.contribution} onChange={(event) => setters.setContribution(event.target.value)}><option value="">Todos</option>{state.contributions.map((item) => <option key={item.id} value={item.id}>{item.code}</option>)}</Select></FormField><FormField label="Fonte de funding"><Select value={values.source} onChange={(event) => setters.setSource(event.target.value)}><option value="">Todas</option>{state.fundingSources.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></FormField><div className="space-y-2 pt-6">{[["Somente divergentes", values.onlyDivergent, setters.setOnlyDivergent], ["Somente com desconto", values.onlyDiscount, setters.setOnlyDiscount], ["Somente com prejuízo", values.onlyLoss, setters.setOnlyLoss], ["Somente não rateados", values.onlyUnallocated, setters.setOnlyUnallocated]].map(([label, checked, setter]) => <label key={String(label)} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(checked)} onChange={(event) => (setter as (value: boolean) => void)(event.target.checked)} />{String(label)}</label>)}</div></CardContent></Card>;
}

function RevenueTableRow({ row, state, navigate, columns, compact }: { row: RevenueRecordView; state: ReturnType<typeof useFundingState>; navigate: (path: string) => void; columns: RevenueColumnKey[]; compact: boolean }) {
  const cells: Record<RevenueColumnKey, ReactNode> = {
    contract: <><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="font-semibold hover:text-primary">{row.contractCode}</AppLink><p className="text-xs text-muted-foreground">{row.maskedClientName}</p></>, installment: `${row.installmentNumber}/${row.totalInstallments ?? "—"}`, dueDate: formatDate(row.dueDate), paymentDate: formatDate(row.operationalPaymentDate), expected: formatCentsAmount(row.expectedInstallmentAmount), paid: formatCentsAmount(row.paidAmount), status: <StatusBadge status={row.operationalStatus} />, operator: row.financialOperator, principal: formatCentsAmount(row.principalAmount), interest: formatCentsAmount(row.interestAmount), iof: formatCentsAmount(row.iofAmount), loss: formatCentsAmount(row.lossAmount), discount: formatCentsAmount(row.discountAmount), apurated: formatCentsAmount(row.apuratedAmount), componentDifference: <span className={cents(row.componentDifference) === 0n ? "text-emerald-400" : "text-rose-400"}>{formatCentsAmount(row.componentDifference)}</span>, paymentReference: <><span>{row.paymentReference.operationalReference}</span><p className="text-xs text-muted-foreground">{row.paymentReference.bankReferences.join(", ") || "Sem referência bancária"}</p></>, funding: <FundingSourcesCell state={state} row={row} />, bankValidation: <StatusBadge status={row.bankValidationStatus} />, revenueStatus: <StatusBadge status={row.revenueStatus} />,
  };
  return <TableRow>{columns.map((column) => <TableCell key={column} className={`${compact ? "px-3 py-2" : "p-4"} ${column === "contract" ? "sticky left-0 z-10 bg-card" : "whitespace-nowrap"}`}>{cells[column]}</TableCell>)}</TableRow>;
}

function FundingSourcesCell({ state, row }: { state: ReturnType<typeof useFundingState>; row: RevenueRecordView }) {
  const allocations = allocationsForRecord(state, row);
  return <details className="min-w-48"><summary className="cursor-pointer font-medium">{row.mainFundingSourceLabel}{row.fundingSourcesCount > 1 ? ` +${row.fundingSourcesCount - 1} fontes` : ""}</summary><div className="mt-2 space-y-1 rounded-lg border bg-popover p-3 text-xs shadow-xl">{allocations.map((allocation) => { const source = state.fundingSources.find((item) => item.id === allocation.fundingSourceId); const investor = state.investors.find((item) => item.id === allocation.investorId); return <div key={allocation.id}><strong>{source?.name ?? allocation.fundingSourceType}</strong><p className="text-muted-foreground">{investor?.name ?? (allocation.fundingSourceType === "REMO_OWN_CAPITAL" ? "Capital próprio REMO" : "Sem investidor")} · {formatCentsAmount(allocation.amount)}</p></div>; })}</div></details>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div><p className="text-xs text-muted-foreground">{label}</p><p className="font-medium">{value}</p></div>; }

function exportRevenue(rows: RevenueRecordView[]) {
  const header = ["id", "contrato", "parcela", "vencimento", "pagamento", "previsto_centavos", "pago_centavos", "principal_centavos", "juros_centavos", "iof_centavos", "status_receita"];
  const lines = rows.map((row) => [row.id, row.contractCode, row.installmentNumber, row.dueDate, row.operationalPaymentDate ?? "", row.expectedInstallmentAmount, row.paidAmount, row.principalAmount, row.interestAmount, row.iofAmount, row.revenueStatus].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(";"));
  const blob = new Blob([[header.join(";"), ...lines].join("\n")], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "receita-demonstrativa.csv"; anchor.click(); URL.revokeObjectURL(url);
}
