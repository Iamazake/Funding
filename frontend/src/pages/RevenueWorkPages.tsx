import { Clock3 } from "lucide-react";
import { useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { ChartCard } from "@/components/charts/FundingCharts";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { revenueDivergenceLabels } from "@/data/revenueOptions";
import { formatCentsAmount } from "@/lib/formatters";
import { cents, sumCents } from "@/repositories/fundingRepository";
import { fundingRepository, useFundingState, useRevenueRecords } from "@/services/fundingService";
import type { ChartPoint, RevenueDivergenceAction, RevenueRecordView } from "@/types/funding";

interface PendingItem { id: string; receiptId: string; reason: string; amount: string; contract: string; installment: number; responsible: string; age: number; nextAction: string; }

export function RevenuePendingPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState(); const records = useRevenueRecords(); const today = new Date("2026-08-04T12:00:00Z");
  const items = records.flatMap((row): PendingItem[] => {
    const result: PendingItem[] = []; const receipt = state.treasuryIncomingReceipts.find((item) => item.id === row.id); if (!receipt) return result;
    const age = Math.max(0, Math.floor((today.getTime() - new Date(row.updatedAt).getTime()) / 86_400_000));
    const add = (reason: string, nextAction: string) => result.push({ id: `${row.id}-${reason}`, receiptId: row.id, reason, amount: row.paidAmount, contract: row.contractCode, installment: row.installmentNumber, responsible: row.financialOperator, age, nextAction });
    if (row.revenueStatus === "PENDING_BANK_VALIDATION") add("Aguardando validação bancária", "Abrir conferência manual na Tesouraria");
    if (["NOT_CALCULATED", "CALCULATED", "REVIEW_REQUIRED"].includes(row.allocationStatus) && row.bankValidationStatus === "VALIDATED") add("Aguardando rateio", row.allocationStatus === "CALCULATED" ? "Confirmar o rateio calculado" : "Recalcular o rateio histórico");
    if (row.componentStatus === "COMPONENTS_MISMATCH") add("Componentes divergentes", "Investigar valores da origem operacional");
    if (row.bankValidationStatus === "MOVEMENT_NOT_FOUND") add("Movimento não encontrado", "Refazer a busca no internet banking");
    if (row.reconciliationStatus === "PARTIAL") add("Pagamento parcial", "Localizar o saldo restante");
    if (row.mainFundingSourceLabel === "Sem composição histórica") add("Sem composição de funding", "Corrigir o vínculo do contrato");
    if (row.allocationStatus === "REVIEW_REQUIRED") add("Composição histórica ausente", "Revisar versões de funding na data da baixa");
    if (row.revenueStatus === "REVERSED" && state.revenueDivergences.some((item) => item.incomingReceiptId === row.id && item.type === "REVERSED_AFTER_ALLOCATION" && item.status !== "RESOLVED")) add("Estorno pendente", "Revisar a distribuição anteriormente calculada");
    return result;
  });
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Pendências" description="Filas de trabalho derivadas do estado atual dos recebimentos, banco e rateios." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{["Aguardando validação bancária", "Aguardando rateio", "Componentes divergentes", "Movimento não encontrado", "Pagamento parcial", "Sem composição de funding", "Composição histórica ausente", "Estorno pendente"].map((reason) => <Card key={reason} className="bg-card/75"><CardContent className="flex items-center gap-3 p-4"><Clock3 className="size-5 text-amber-400" /><div><p className="text-2xl font-semibold">{items.filter((item) => item.reason === reason).length}</p><p className="text-xs text-muted-foreground">{reason}</p></div></CardContent></Card>)}</div>
    <SimpleTable headers={["Motivo", "Valor", "Contrato", "Parcela", "Responsável", "Idade", "Próxima ação"]}>{items.map((item) => <TableRow key={item.id}><TableCell className="font-medium">{item.reason}</TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell><AppLink to={`/receita/${item.receiptId}`} onNavigate={navigate} className="hover:text-primary">{item.contract}</AppLink></TableCell><TableCell>{item.installment}</TableCell><TableCell>{item.responsible}</TableCell><TableCell>{item.age} dia(s)</TableCell><TableCell>{item.nextAction}</TableCell></TableRow>)}</SimpleTable>
  </div>;
}

export function RevenueDivergencesPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState(); const records = useRevenueRecords(); const [notes, setNotes] = useState<Record<string, string>>({});
  const act = (id: string, action: RevenueDivergenceAction) => fundingRepository.updateRevenueDivergence(id, action, notes[id] ?? "Ação demonstrativa registrada.", "Analista de Receita Demo");
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Divergências" description="Investigações preservadas; nenhuma divergência é excluída definitivamente." />
    <SimpleTable headers={["Recebimento", "Tipo", "Esperado", "Encontrado", "Diferença", "Status", "Observação", "Ações"]}>{state.revenueDivergences.map((item) => { const record = records.find((row) => row.id === item.incomingReceiptId); return <TableRow key={item.id}><TableCell><AppLink to={`/receita/${item.incomingReceiptId}`} onNavigate={navigate} className="font-medium hover:text-primary">{record?.contractCode ?? item.incomingReceiptId}</AppLink><p className="text-xs text-muted-foreground">Parcela {record?.installmentNumber ?? "—"}</p></TableCell><TableCell>{revenueDivergenceLabels[item.type]}</TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.actualAmount)}</TableCell><TableCell>{formatCentsAmount(item.differenceAmount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell><Input value={notes[item.id] ?? item.resolutionNotes ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Adicionar observação…" /></TableCell><TableCell><div className="flex min-w-[310px] flex-wrap gap-1"><Button size="sm" variant="ghost" onClick={() => act(item.id, "INVESTIGATE")}>Investigar</Button><Button size="sm" variant="ghost" onClick={() => act(item.id, "ADD_NOTE")}>Salvar nota</Button><Button size="sm" variant="ghost" onClick={() => act(item.id, "FIX_LINK")}>Corrigir vínculo</Button><Button size="sm" variant="ghost" disabled={record?.bankValidationStatus !== "VALIDATED"} onClick={() => { if (record) fundingRepository.recalculateRevenueAllocation(record.id, "Analista de Receita Demo"); act(item.id, "RECALCULATE"); }}>Recalcular</Button><Button size="sm" variant="ghost" onClick={() => act(item.id, "JUSTIFY")}>Justificar</Button><Button size="sm" variant="ghost" onClick={() => act(item.id, "RESOLVE")}>Resolver</Button><Button size="sm" variant="ghost" onClick={() => act(item.id, "REOPEN")}>Reabrir</Button></div></TableCell></TableRow>; })}</SimpleTable>
  </div>;
}

interface MonthlyRow { competence: string; expected: string; paid: string; principal: string; interest: string; iof: string; penalty: string; discount: string; loss: string; apurated: string; divergence: string; count: number; validated: number; pending: number; }

export function RevenueMonthlySummaryPage() {
  const state = useFundingState(); const records = useRevenueRecords(); const [competence, setCompetence] = useState("");
  const monthly = useMemo(() => {
    const groups = new Map<string, RevenueRecordView[]>(); records.forEach((row) => groups.set(row.paymentReference.competence, [...(groups.get(row.paymentReference.competence) ?? []), row]));
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([key, rows]): MonthlyRow => ({ competence: key, expected: sumCents(rows.map((row) => row.expectedInstallmentAmount)), paid: sumCents(rows.map((row) => row.paidAmount)), principal: sumCents(rows.map((row) => row.principalAmount)), interest: sumCents(rows.map((row) => row.interestAmount)), iof: sumCents(rows.map((row) => row.iofAmount)), penalty: sumCents(rows.map((row) => row.penaltyAmount)), discount: sumCents(rows.map((row) => row.discountAmount)), loss: sumCents(rows.map((row) => row.lossAmount)), apurated: sumCents(rows.map((row) => row.apuratedAmount)), divergence: rows.reduce((sum, row) => sum + (cents(row.componentDifference) < 0n ? -cents(row.componentDifference) : cents(row.componentDifference)), 0n).toString(), count: rows.length, validated: rows.filter((row) => row.revenueStatus === "VALIDATED").length, pending: rows.filter((row) => row.revenueStatus !== "VALIDATED").length }));
  }, [records]);
  const rows = competence ? monthly.filter((item) => item.competence === competence) : monthly;
  const visibleRecords = competence ? records.filter((item) => item.paymentReference.competence === competence) : records;
  const visibleReceiptIds = new Set(visibleRecords.map((item) => item.id));
  const chart = (primary: keyof MonthlyRow, secondary?: keyof MonthlyRow): ChartPoint[] => rows.map((row) => ({ label: row.competence, value: chartMoney(row[primary]), secondaryValue: secondary ? chartMoney(row[secondary]) : undefined }));
  const sourceTotals = new Map<string, bigint>();
  state.allocationReceiptShares.filter((item) => item.status !== "REVERSED" && visibleReceiptIds.has(item.incomingReceiptId)).forEach((share) => { const allocation = state.contractFundingAllocations.find((item) => item.id === share.contractFundingAllocationId); const source = state.fundingSources.find((item) => item.id === allocation?.fundingSourceId); const amount = cents(share.principalShare) + cents(share.interestShare) + cents(share.penaltyShare) - cents(share.discountShare) - cents(share.lossShare); sourceTotals.set(source?.name ?? share.fundingSourceType, (sourceTotals.get(source?.name ?? share.fundingSourceType) ?? 0n) + amount); });
  const validationPoints: ChartPoint[] = ["PENDING", "VALUE_MISMATCH", "MOVEMENT_NOT_FOUND", "VALIDATED"].map((status) => ({ label: status.replaceAll("_", " "), value: visibleRecords.filter((row) => row.bankValidationStatus === status).length }));
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Resumo mensal" description="Consolidação analítica em bigint; valores dos gráficos são conversões apenas de apresentação." actions={<Input className="w-48" type="month" value={competence} onChange={(event) => setCompetence(event.target.value)} />} />
    <SimpleTable headers={["Competência", "PMT prevista", "Valor pago", "Principal", "Juros", "IOF", "Multa", "Desconto", "Prejuízo", "Total apurado", "Divergência", "Parcelas", "Validadas", "Pendentes"]}>{rows.map((row) => <TableRow key={row.competence}><TableCell className="font-medium">{row.competence}</TableCell>{(["expected", "paid", "principal", "interest", "iof", "penalty", "discount", "loss", "apurated", "divergence"] as const).map((field) => <TableCell key={field}>{formatCentsAmount(row[field])}</TableCell>)}<TableCell>{row.count}</TableCell><TableCell>{row.validated}</TableCell><TableCell>{row.pending}</TableCell></TableRow>)}</SimpleTable>
    <div className="grid gap-5 xl:grid-cols-2"><ChartCard title="Recebido por competência" description="Valor operacional pago por mês." data={chart("paid")} variant="bar" primaryLabel="Recebido" /><ChartCard title="Principal versus juros" description="Recuperação de principal separada da receita financeira." data={chart("principal", "interest")} primaryLabel="Principal" secondaryLabel="Juros" /><ChartCard title="Previsto versus pago" description="PMT prevista comparada ao pagamento operacional." data={chart("expected", "paid")} primaryLabel="Previsto" secondaryLabel="Pago" /><ChartCard title="Descontos e prejuízos" description="Reduções registradas na composição da parcela." data={chart("discount", "loss")} primaryLabel="Desconto" secondaryLabel="Prejuízo" /><ChartCard title="Receita por fonte de funding" description="Componentes rateáveis atribuídos por fonte; IOF permanece fora." data={[...sourceTotals].map(([label, value]) => ({ label, value: chartMoney(value.toString()) }))} variant="donut" /><ChartCard title="Validações bancárias por status" description="Mesmos status exibidos em Tesouraria > Entradas." data={validationPoints} variant="bar" /></div>
  </div>;
}

function chartMoney(value: string | number): number { return typeof value === "number" ? value : Number(cents(value) / 100n); }
function SimpleTable({ headers, children }: { headers: string[]; children: React.ReactNode }) { return <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{children}</TableBody></Table></Card>; }
