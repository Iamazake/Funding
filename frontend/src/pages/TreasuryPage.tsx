import { ArrowDownLeft, ArrowUpRight, Banknote, Landmark, Plus, RefreshCw, RotateCcw, Scale, Wallet } from "lucide-react";
import { useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs, type TabItem } from "@/components/common/Tabs";
import { TreasuryEntryFormModal } from "@/components/funding/TreasuryEntryFormModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { currencyInputToCents, formatCentsAmount, formatDate } from "@/lib/formatters";
import { fundingRepository, getTreasurySummary, useFundingState } from "@/services/fundingService";
import type { ReconciliationInput, TreasuryEntry, TreasuryEntryInput } from "@/types/funding";

export type TreasurySection = "summary" | "exits" | "remunerations" | "reconciliation" | "divergences";
const tabs: TabItem[] = [
  { value: "summary", label: "Visão geral", path: "/tesouraria" },
  { value: "entries", label: "Entradas", path: "/tesouraria/entradas" },
  { value: "exits", label: "Saídas", path: "/tesouraria/saidas" },
  { value: "remunerations", label: "Remunerações", path: "/tesouraria/remuneracoes" },
  { value: "reconciliation", label: "Conciliação", path: "/tesouraria/conciliacao" },
  { value: "divergences", label: "Divergências", path: "/tesouraria/divergencias" },
];

export function TreasuryPage({ section = "summary", navigate }: { section?: TreasurySection; navigate: (path: string) => void }) {
  const state = useFundingState(); const [feedback, setFeedback] = useState<Feedback | null>(null);
  const rows = section === "exits" ? state.treasuryEntries.filter((item) => item.direction === "SAIDA")
    : state.treasuryEntries.filter((item) => ["CAPITAL_REMUNERATION_PAID", "PJR_PAYMENT", "REMUNERATION_REINVESTED"].includes(item.type));
  return <div className="space-y-6"><PageHeader eyebrow="Tesouraria" title="Livro integrado de caixa" description="Entradas esperadas, entradas confirmadas, saídas e transferências internas possuem eventos separados." /><FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} /><Tabs items={tabs} value={section} navigate={navigate} />
    {section === "summary" && <Summary />}{["exits", "remunerations"].includes(section) && <Movements rows={rows} setFeedback={setFeedback} />}{section === "reconciliation" && <Reconciliation setFeedback={setFeedback} />}{section === "divergences" && <Divergences navigate={navigate} />}
  </div>;
}

function Summary() {
  const summary = getTreasurySummary();
  return <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Landmark} label="Principal administrado" value={formatCentsAmount(summary.principalManaged)} /><KpiCard compact icon={Wallet} label="Saldo disponível dos aportes" value={formatCentsAmount(summary.availableBalance)} /><KpiCard compact icon={Scale} label="Reserva contábil" value={formatCentsAmount(summary.allocatedCapital)} /><KpiCard compact icon={Banknote} label="Saldo de caixa" value={formatCentsAmount(summary.cashBalance)} /></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={ArrowDownLeft} label="Principal recebido validado" value={formatCentsAmount(summary.accumulatedCapital)} /><KpiCard compact icon={ArrowDownLeft} label="Juros recebidos validados" value={formatCentsAmount(summary.accumulatedInterest)} /><KpiCard compact icon={ArrowUpRight} label="Remuneração pendente" value={formatCentsAmount(summary.pendingPayments)} /><KpiCard compact icon={RefreshCw} label="Remuneração reinvestida" value={formatCentsAmount(summary.reinvestedInterest)} /></div></>;
}

function Movements({ rows, setFeedback }: { rows: TreasuryEntry[]; setFeedback: (value: Feedback) => void }) {
  const state = useFundingState(); const [open, setOpen] = useState(false); const [reverse, setReverse] = useState<string | null>(null);
  const save = (input: TreasuryEntryInput) => { fundingRepository.createTreasuryEntry(input); setOpen(false); setFeedback({ tone: "success", message: "Movimento demonstrativo criado." }); };
  return <><div className="flex justify-end"><Button onClick={() => setOpen(true)}><Plus className="size-4" />Nova movimentação</Button></div><Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Data</TableHead><TableHead>Tipo</TableHead><TableHead>Natureza</TableHead><TableHead>Valor</TableHead><TableHead>Conta</TableHead><TableHead>Status</TableHead><TableHead>Responsável</TableHead><TableHead>Referência</TableHead><TableHead>Ação</TableHead></TableRow></TableHeader><TableBody>{rows.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.date)}</TableCell><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell><StatusBadge status={item.direction} /></TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell>{item.cashAccount}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.owner}</TableCell><TableCell>{item.reference}<p className="text-xs text-muted-foreground">{item.notes}</p></TableCell><TableCell>{item.status === "CONFIRMADO" && <Button size="icon" variant="ghost" onClick={() => setReverse(item.id)}><RotateCcw className="size-4" /></Button>}</TableCell></TableRow>)}</TableBody></Table></Card><TreasuryEntryFormModal open={open} investors={state.investors} contributions={state.contributions} onClose={() => setOpen(false)} onSave={save} /><ConfirmDialog open={reverse !== null} title="Estornar movimento?" description="O original permanecerá no livro e uma contrapartida será criada." confirmLabel="Criar estorno" onCancel={() => setReverse(null)} onConfirm={() => { if (reverse) fundingRepository.reverseTreasuryEntry(reverse, { date: "2026-08-04", owner: "Tesouraria Demo", notes: "Estorno solicitado manualmente." }); setReverse(null); }} /></>;
}

function Reconciliation({ setFeedback }: { setFeedback: (value: Feedback) => void }) {
  const state = useFundingState(); const [open, setOpen] = useState(false); const [amount, setAmount] = useState(""); const [notes, setNotes] = useState("");
  const save = () => { const parsed = currencyInputToCents(amount); if (parsed === null) return; const input: ReconciliationInput = { cashAccount: "Conta Caixa Demo 01", informedBalance: parsed, date: "2026-08-04", owner: "Tesouraria Demo", notes }; fundingRepository.reconcile(input); setOpen(false); setFeedback({ tone: "success", message: "Conciliação registrada." }); };
  return <><div className="flex justify-end"><Button onClick={() => setOpen(true)}>Nova conciliação</Button></div><Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Data / conta</TableHead><TableHead>Calculado</TableHead><TableHead>Informado</TableHead><TableHead>Diferença</TableHead><TableHead>Status</TableHead><TableHead>Notas</TableHead></TableRow></TableHeader><TableBody>{state.reconciliations.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.date)}<p>{item.cashAccount}</p></TableCell><TableCell>{formatCentsAmount(item.calculatedBalance)}</TableCell><TableCell>{formatCentsAmount(item.informedBalance)}</TableCell><TableCell>{formatCentsAmount(item.difference)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.notes}</TableCell></TableRow>)}</TableBody></Table></Card><Modal open={open} title="Conciliação demonstrativa" description="Saldo conferido manualmente, sem conexão bancária." onClose={() => setOpen(false)} footer={<Button onClick={save}>Registrar</Button>}><div className="space-y-4"><FormField label="Saldo informado"><Input value={amount} onChange={(event) => setAmount(event.target.value)} /></FormField><FormField label="Notas"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></FormField></div></Modal></>;
}

function Divergences({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  return state.treasuryDivergences.length === 0 ? <Card><CardContent className="p-6 text-sm text-muted-foreground">Nenhuma divergência bancária registrada.</CardContent></Card> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Entrada</TableHead><TableHead>Tipo</TableHead><TableHead>Esperado</TableHead><TableHead>Conciliado</TableHead><TableHead>Diferença</TableHead><TableHead>Status</TableHead><TableHead>Histórico</TableHead></TableRow></TableHeader><TableBody>{state.treasuryDivergences.map((item) => { const receipt = state.treasuryIncomingReceipts.find((value) => value.id === item.incomingReceiptId); return <TableRow key={item.id}><TableCell><AppLink to={`/tesouraria/entradas/${item.incomingReceiptId}`} onNavigate={navigate} className="font-medium hover:text-primary">{receipt?.contractCode}</AppLink><p className="text-xs text-muted-foreground">Parcela {receipt?.installmentNumber}</p></TableCell><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.reconciledAmount)}</TableCell><TableCell>{formatCentsAmount(item.differenceAmount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.resolutionNotes ?? item.description}</TableCell></TableRow>; })}</TableBody></Table></Card>;
}
