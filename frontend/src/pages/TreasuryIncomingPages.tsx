import { AlertTriangle, ArrowLeft, Banknote, CheckCircle2, Clock3, Unlink } from "lucide-react";
import { useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { currencyInputToCents, formatCentsAmount, formatDate, formatDateTime } from "@/lib/formatters";
import { cents, sumCents } from "@/repositories/fundingRepository";
import { fundingRepository, useFundingState } from "@/services/fundingService";
import type { BankMovementInput, ReceiptBankReconciliationInput, TreasuryIncomingReceipt } from "@/types/funding";

function activeLinks(state: ReturnType<typeof useFundingState>, receiptId: string) {
  return state.receiptBankReconciliations.filter((item) => item.incomingReceiptId === receiptId && item.status === "ACTIVE");
}

function reconciledAmount(state: ReturnType<typeof useFundingState>, receiptId: string): string {
  return sumCents(activeLinks(state, receiptId).map((item) => item.amount));
}

function targetAmount(receipt: TreasuryIncomingReceipt): string {
  return cents(receipt.paidAmountFromOperationalSource) > 0n ? receipt.paidAmountFromOperationalSource : receipt.expectedAmount;
}

const filterStatusLabels: Record<string, string> = {
  WAITING_OPERATIONAL_WRITE_OFF: "Aguardando baixa operacional", WAITING_BANK_VALIDATION: "Aguardando validação bancária",
  BANK_MOVEMENT_FOUND: "Movimento encontrado", BANK_VALUE_MISMATCH: "Valor bancário divergente",
  BANK_MOVEMENT_NOT_FOUND: "Movimento não encontrado", PARTIALLY_VALIDATED: "Validada parcialmente",
  VALIDATED: "Validada", REVERSED: "Estornada", CANCELLED: "Cancelada", PENDING: "Pendente",
  MOVEMENT_FOUND: "Movimento encontrado", VALUE_MISMATCH: "Valor divergente", MOVEMENT_NOT_FOUND: "Movimento não encontrado",
  REJECTED: "Rejeitada",
};

function filterStatusLabel(status: string): string {
  return filterStatusLabels[status] ?? status;
}

function differenceAmount(state: ReturnType<typeof useFundingState>, receipt: TreasuryIncomingReceipt): string {
  return (cents(targetAmount(receipt)) - cents(reconciledAmount(state, receipt.id))).toString();
}

export function TreasuryIncomingListPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  const [from, setFrom] = useState("2026-07-01"); const [to, setTo] = useState("2026-08-31");
  const [contract, setContract] = useState(""); const [installment, setInstallment] = useState("");
  const [status, setStatus] = useState(""); const [bankStatus, setBankStatus] = useState("");
  const [account, setAccount] = useState(""); const [responsible, setResponsible] = useState("");
  const [onlyDivergent, setOnlyDivergent] = useState(false);
  const rows = useMemo(() => state.treasuryIncomingReceipts.filter((item) => {
    const movementAccounts = activeLinks(state, item.id).map((link) => state.bankMovements.find((movement) => movement.id === link.bankMovementId)?.bankAccountId);
    const divergent = ["BANK_VALUE_MISMATCH", "BANK_MOVEMENT_NOT_FOUND", "PARTIALLY_VALIDATED"].includes(item.status) || item.reconciliationStatus === "DIVERGENT";
    return (!from || item.dueDate >= from) && (!to || item.dueDate <= to)
      && (!contract || item.contractCode.toLowerCase().includes(contract.toLowerCase()))
      && (!installment || String(item.installmentNumber) === installment)
      && (!status || item.status === status) && (!bankStatus || item.bankValidationStatus === bankStatus)
      && (!account || movementAccounts.includes(account))
      && (!responsible || item.responsibleUser.toLowerCase().includes(responsible.toLowerCase()))
      && (!onlyDivergent || divergent);
  }), [account, bankStatus, contract, from, installment, onlyDivergent, responsible, state, status, to]);
  const expected = sumCents(rows.map((item) => item.expectedAmount));
  const totalDifference = rows.reduce((sum, item) => sum + (cents(differenceAmount(state, item)) < 0n ? -cents(differenceAmount(state, item)) : cents(differenceAmount(state, item))), 0n).toString();
  const isDivergent = (item: TreasuryIncomingReceipt) => ["BANK_VALUE_MISMATCH", "BANK_MOVEMENT_NOT_FOUND", "PARTIALLY_VALIDATED"].includes(item.status) || item.reconciliationStatus === "DIVERGENT";
  return <div className="space-y-6">
    <PageHeader eyebrow="Receita · entradas" title="Validação bancária" description="Conferência manual dos recebimentos e baixas de PMTs demonstrativas." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Clock3} label="Entradas previstas" value={String(rows.length)} /><KpiCard compact icon={CheckCircle2} label="Entradas baixadas" value={String(rows.filter((item) => item.operationalStatus === "WRITTEN_OFF").length)} /><KpiCard compact icon={Clock3} label="Aguardando validação" value={String(rows.filter((item) => item.status === "WAITING_BANK_VALIDATION").length)} /><KpiCard compact icon={CheckCircle2} label="Validadas" value={String(rows.filter((item) => item.status === "VALIDATED").length)} /><KpiCard compact icon={AlertTriangle} label="Divergentes" value={String(rows.filter(isDivergent).length)} /><KpiCard compact icon={Unlink} label="Não encontradas" value={String(rows.filter((item) => item.status === "BANK_MOVEMENT_NOT_FOUND").length)} /><KpiCard compact icon={Banknote} label="Valor total do período" value={formatCentsAmount(expected)} /><KpiCard compact icon={AlertTriangle} label="Diferença bancária total" value={formatCentsAmount(totalDifference)} /></div>
    <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Filtros</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><FormField label="De"><Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></FormField><FormField label="Até"><Input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></FormField><FormField label="Contrato"><Input value={contract} onChange={(event) => setContract(event.target.value)} /></FormField><FormField label="Parcela"><Input inputMode="numeric" value={installment} onChange={(event) => setInstallment(event.target.value.replace(/\D/g, ""))} /></FormField><FormField label="Status"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Todos</option>{["WAITING_OPERATIONAL_WRITE_OFF", "WAITING_BANK_VALIDATION", "BANK_MOVEMENT_FOUND", "BANK_VALUE_MISMATCH", "BANK_MOVEMENT_NOT_FOUND", "PARTIALLY_VALIDATED", "VALIDATED", "REVERSED", "CANCELLED"].map((item) => <option key={item} value={item}>{filterStatusLabel(item)}</option>)}</Select></FormField><FormField label="Validação bancária"><Select value={bankStatus} onChange={(event) => setBankStatus(event.target.value)}><option value="">Todas</option>{["PENDING", "MOVEMENT_FOUND", "VALUE_MISMATCH", "MOVEMENT_NOT_FOUND", "VALIDATED", "REJECTED"].map((item) => <option key={item} value={item}>{filterStatusLabel(item)}</option>)}</Select></FormField><FormField label="Conta"><Select value={account} onChange={(event) => setAccount(event.target.value)}><option value="">Todas</option>{[...new Set(state.bankMovements.map((item) => item.bankAccountId))].map((item) => <option key={item}>{item}</option>)}</Select></FormField><FormField label="Responsável"><Input value={responsible} onChange={(event) => setResponsible(event.target.value)} /></FormField><label className="flex items-center gap-2 pt-7 text-sm"><input type="checkbox" checked={onlyDivergent} onChange={(event) => setOnlyDivergent(event.target.checked)} />Somente divergentes</label></CardContent></Card>
    <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Parcela</TableHead><TableHead>Vencimento / baixa</TableHead><TableHead>Previsto</TableHead><TableHead>Pago informado</TableHead><TableHead>Principal / juros / IOF</TableHead><TableHead>Desconto</TableHead><TableHead>Operacional</TableHead><TableHead>Banco</TableHead><TableHead>Diferença</TableHead><TableHead>Responsável</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{rows.map((item) => <TableRow key={item.id} className="cursor-pointer" onClick={() => navigate(`/receita/${item.id}`)}><TableCell><AppLink to={`/receita/${item.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{item.contractCode}</AppLink><p className="text-xs text-muted-foreground">{item.maskedClientName}</p></TableCell><TableCell>{item.installmentNumber}/{item.totalInstallments}</TableCell><TableCell>{formatDate(item.dueDate)}<p className="text-xs text-muted-foreground">Baixa: {formatDate(item.operationalWriteOffDate)}</p></TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.paidAmountFromOperationalSource)}</TableCell><TableCell>{formatCentsAmount(item.principalAmount)}<p className="text-xs text-muted-foreground">{formatCentsAmount(item.interestAmount)} · {formatCentsAmount(item.iofAmount)}</p></TableCell><TableCell>{formatCentsAmount(item.discountAmount)}</TableCell><TableCell><StatusBadge status={item.operationalStatus} /></TableCell><TableCell><StatusBadge status={item.bankValidationStatus} /></TableCell><TableCell>{formatCentsAmount(differenceAmount(state, item))}</TableCell><TableCell>{item.responsibleUser}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</TableBody></Table></Card>
  </div>;
}

const detailTabs = [
  { value: "summary", label: "Resumo" }, { value: "installment", label: "Dados da parcela" },
  { value: "bank", label: "Validação bancária" }, { value: "movements", label: "Movimentos conciliados" },
  { value: "shares", label: "Rateio do recebimento" }, { value: "divergences", label: "Divergências" },
  { value: "history", label: "Histórico" },
];

export function TreasuryIncomingDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const state = useFundingState(); const receipt = state.treasuryIncomingReceipts.find((item) => item.id === id);
  const [tab, setTab] = useState("summary"); const [validationOpen, setValidationOpen] = useState(false); const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (!receipt) return <EmptyState title="Entrada esperada não encontrada" />;
  const links = activeLinks(state, id); const movements = links.map((link) => ({ link, movement: state.bankMovements.find((item) => item.id === link.bankMovementId) })).filter((item) => item.movement);
  const shares = state.allocationReceiptShares.filter((item) => item.incomingReceiptId === id);
  const divergences = state.treasuryDivergences.filter((item) => item.incomingReceiptId === id);
  const history = state.auditEvents.filter((item) => item.entityId === id || links.some((link) => link.bankMovementId === item.entityId) || divergences.some((divergence) => divergence.id === item.entityId));
  return <div className="space-y-6">
    <AppLink to="/receita/validacao-bancaria" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para validação bancária</AppLink>
    <PageHeader eyebrow={`${receipt.contractCode} · parcela ${receipt.installmentNumber}/${receipt.totalInstallments}`} title={receipt.maskedClientName} description="Entrada esperada originada de baixa operacional fictícia, separada do contrato e da liberação do empréstimo." actions={<StatusBadge status={receipt.status} />} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <Tabs items={detailTabs} value={tab} onChange={setTab} />
    {tab === "summary" && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Banknote} label="Valor esperado" value={formatCentsAmount(targetAmount(receipt))} /><KpiCard compact icon={CheckCircle2} label="Total conciliado" value={formatCentsAmount(reconciledAmount(state, id))} /><KpiCard compact icon={AlertTriangle} label="Saldo não localizado" value={formatCentsAmount(differenceAmount(state, receipt))} /><KpiCard compact icon={Clock3} label="Baixa operacional" value={formatDate(receipt.operationalWriteOffDate)} /></div>}
    {tab === "installment" && <SimpleTable headers={["Vencimento", "Baixa", "Previsto", "Pago", "Principal", "Juros", "IOF", "Multa", "Desconto", "Prejuízo", "Referência"]}><TableRow><TableCell>{formatDate(receipt.dueDate)}</TableCell><TableCell>{formatDate(receipt.operationalWriteOffDate)}</TableCell><TableCell>{formatCentsAmount(receipt.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.paidAmountFromOperationalSource)}</TableCell><TableCell>{formatCentsAmount(receipt.principalAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.interestAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.iofAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.penaltyAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.discountAmount)}</TableCell><TableCell>{formatCentsAmount(receipt.lossAmount)}</TableCell><TableCell>{receipt.sourceReference}</TableCell></TableRow></SimpleTable>}
    {tab === "bank" && <><div className="flex justify-end"><Button disabled={receipt.operationalStatus !== "WRITTEN_OFF"} onClick={() => setValidationOpen(true)}>Registrar conferência manual</Button></div><p className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm text-muted-foreground">A conferência não altera silenciosamente a baixa operacional. Diferenças permanecem em divergência.</p></>}
    {tab === "movements" && <SimpleTable headers={["Data", "Conta", "Valor do movimento", "Associado a esta entrada", "Referência", "Pagador", "Conferido por", "Status", "Ação"]}>{movements.map(({ link, movement }) => movement && <TableRow key={link.id}><TableCell>{formatDate(movement.movementDate)}</TableCell><TableCell>{movement.bankAccountId}</TableCell><TableCell>{formatCentsAmount(movement.amount)}</TableCell><TableCell>{formatCentsAmount(link.amount)}</TableCell><TableCell>{movement.transactionReference}</TableCell><TableCell>{movement.payerDescription}</TableCell><TableCell>{movement.checkedBy}<p className="text-xs text-muted-foreground">{formatDateTime(movement.checkedAt)}</p></TableCell><TableCell><StatusBadge status={movement.status} /></TableCell><TableCell><Button size="sm" variant="ghost" onClick={() => { fundingRepository.reverseBankMovement(movement.id, { date: "2026-08-04", owner: "Tesouraria Demo", notes: "Estorno manual demonstrativo." }); setFeedback({ tone: "success", message: "Movimento estornado com histórico preservado." }); }}>Estornar</Button></TableCell></TableRow>)}</SimpleTable>}
    {tab === "shares" && <><p className="text-sm text-muted-foreground">Regra demonstrativa: composição de funding válida na data da baixa operacional ({formatDate(receipt.operationalWriteOffDate ?? receipt.dueDate)}), com bigint, soma exata e resto determinístico.</p><SimpleTable headers={["Fonte", "Investidor / aporte", "Participação", "Principal", "Juros", "IOF", "Multa", "Desconto", "Prejuízo"]}>{shares.map((share) => { const allocation = state.contractFundingAllocations.find((item) => item.id === share.contractFundingAllocationId); const source = state.fundingSources.find((item) => item.id === allocation?.fundingSourceId); const investor = state.investors.find((item) => item.id === share.investorId); const contribution = state.contributions.find((item) => item.id === share.contributionId); return <TableRow key={share.id}><TableCell>{source?.name ?? share.fundingSourceType.replaceAll("_", " ")}</TableCell><TableCell>{investor?.name ?? (share.fundingSourceType === "REMO_OWN_CAPITAL" ? "Capital próprio REMO" : "—")}<p className="text-xs text-muted-foreground">{contribution?.code}</p></TableCell><TableCell>{share.allocationBps} bps</TableCell><TableCell>{formatCentsAmount(share.principalShare)}</TableCell><TableCell>{formatCentsAmount(share.interestShare)}</TableCell><TableCell>{formatCentsAmount(share.iofShare)}</TableCell><TableCell>{formatCentsAmount(share.penaltyShare)}</TableCell><TableCell>{formatCentsAmount(share.discountShare)}</TableCell><TableCell>{formatCentsAmount(share.lossShare)}</TableCell></TableRow>; })}</SimpleTable></>}
    {tab === "divergences" && <SimpleTable headers={["Tipo", "Esperado", "Conciliado", "Diferença", "Situação", "Histórico"]}>{divergences.map((item) => <TableRow key={item.id}><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.reconciledAmount)}</TableCell><TableCell>{formatCentsAmount(item.differenceAmount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.resolutionNotes ?? item.description}</TableCell></TableRow>)}</SimpleTable>}
    {tab === "history" && <Card className="bg-card/75"><CardContent className="space-y-4 p-6">{history.map((item) => <div key={item.id}><p className="text-sm">{item.description}</p><p className="text-xs text-muted-foreground">{formatDateTime(item.date)} · {item.demoUser}</p></div>)}</CardContent></Card>}
    <BankReconciliationModal open={validationOpen} primaryReceiptId={id} onClose={() => setValidationOpen(false)} onSaved={() => { setValidationOpen(false); setFeedback({ tone: "success", message: "Conferência e associações bancárias registradas." }); }} />
  </div>;
}

function BankReconciliationModal({ open, primaryReceiptId, onClose, onSaved }: { open: boolean; primaryReceiptId: string; onClose: () => void; onSaved: () => void }) {
  const state = useFundingState(); const primary = state.treasuryIncomingReceipts.find((item) => item.id === primaryReceiptId);
  const [found, setFound] = useState<"FOUND" | "NOT_FOUND">("FOUND"); const [account, setAccount] = useState("Conta Caixa Demo 01");
  const [date, setDate] = useState("2026-08-04"); const [amount, setAmount] = useState(""); const [reference, setReference] = useState("");
  const [payer, setPayer] = useState("Pagador ***"); const [responsible, setResponsible] = useState("Conferente Demo");
  const [checkedAt, setCheckedAt] = useState("2026-08-04T12:00"); const [notes, setNotes] = useState("");
  const [selected, setSelected] = useState<Record<string, string>>({ [primaryReceiptId]: "" });
  const parsedAmount = currencyInputToCents(amount);
  const linkedValues = Object.values(selected).map((value) => currencyInputToCents(value) ?? "0");
  const hasPositiveLink = linkedValues.some((value) => cents(value) > 0n);
  const canSave = Boolean(primary && checkedAt && responsible.trim() && Object.keys(selected).length > 0
    && (found === "NOT_FOUND" || (parsedAmount !== null && cents(parsedAmount) > 0n && hasPositiveLink)));
  const save = () => {
    if (!primary || parsedAmount === null || !canSave) return;
    const links: ReceiptBankReconciliationInput[] = Object.entries(selected).map(([incomingReceiptId, linked]) => ({ incomingReceiptId, amount: found === "FOUND" ? currencyInputToCents(linked) ?? "0" : "0", notes: "Associação confirmada manualmente." }));
    const input: BankMovementInput = { bankAccountId: account, movementDate: date, amount: found === "FOUND" ? parsedAmount : "0", transactionReference: reference, payerDescription: payer, checkedBy: responsible, checkedAt: new Date(checkedAt).toISOString(), status: found, notes };
    fundingRepository.reconcileBankMovement(input, links); onSaved();
  };
  return <Modal open={open} title="Conferência bancária manual" description="Um movimento pode ser associado explicitamente a uma ou várias entradas; pagamentos parciais são permitidos." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!canSave} onClick={save}>Registrar conferência</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2"><FormField label="Resultado"><Select value={found} onChange={(event) => setFound(event.target.value as "FOUND" | "NOT_FOUND")}><option value="FOUND">Movimento encontrado</option><option value="NOT_FOUND">Movimento não encontrado</option></Select></FormField><FormField label="Conta bancária"><Input value={account} onChange={(event) => setAccount(event.target.value)} /></FormField><FormField label="Data do movimento"><Input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></FormField><FormField label="Valor encontrado"><Input disabled={found === "NOT_FOUND"} value={amount} onChange={(event) => setAmount(event.target.value)} /></FormField><FormField label="Referência / transação"><Input value={reference} onChange={(event) => setReference(event.target.value)} /></FormField><FormField label="Descrição do pagador"><Input value={payer} onChange={(event) => setPayer(event.target.value)} /></FormField><FormField label="Responsável"><Input value={responsible} onChange={(event) => setResponsible(event.target.value)} /></FormField><FormField label="Data e hora da conferência"><Input type="datetime-local" value={checkedAt} onChange={(event) => setCheckedAt(event.target.value)} /></FormField><FormField label="Observação" className="sm:col-span-2"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></FormField></div>
    <div className="mt-5 space-y-3"><p className="text-sm font-medium">Associações N:N confirmadas</p>{state.treasuryIncomingReceipts.filter((item) => item.operationalStatus === "WRITTEN_OFF" && item.status !== "CANCELLED").map((item) => { const checked = item.id in selected; return <div key={item.id} className="grid gap-3 rounded-xl border p-3 sm:grid-cols-[auto_1fr_180px]"><input type="checkbox" checked={checked} onChange={(event) => setSelected((current) => { const next = { ...current }; if (event.target.checked) next[item.id] = ""; else delete next[item.id]; return next; })} /><div className="text-sm"><strong>{item.contractCode} · parcela {item.installmentNumber}</strong><p className="text-xs text-muted-foreground">Saldo: {formatCentsAmount(differenceAmount(state, item))}</p></div><Input disabled={!checked || found === "NOT_FOUND"} value={selected[item.id] ?? ""} onChange={(event) => setSelected((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Valor associado" /></div>; })}</div>
  </Modal>;
}

function SimpleTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{children}</TableBody></Table></Card>;
}
