import { useEffect, useMemo, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/formatters";
import { brazilianMoneyToDecimal, decimalMoneyToCents, formatMonthlyRate } from "@/lib/fundingFormat";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import type { FundingSource } from "@/types/fundingApi";

export interface SaleAllocationInput {
  source_id: string;
  amount: string;
  notes: string | null;
}

export function SaleFundingAllocationModal({ open, sources, historicalBalances, saving, onClose, onSave }: { open: boolean; sources: FundingSource[]; historicalBalances: Record<string, string>; saving: boolean; onClose: () => void; onSave: (input: SaleAllocationInput) => void }) {
  const active = useMemo(() => sources.filter((source) => source.status === "ACTIVE"), [sources]);
  const [sourceId, setSourceId] = useState("");
  const [amountInput, setAmountInput] = useState("");
  const [notes, setNotes] = useState("");
  useEffect(() => { if (open) { setSourceId(active[0]?.id ?? ""); setAmountInput(""); setNotes(""); } }, [open, active]);
  const amount = brazilianMoneyToDecimal(amountInput);
  const selectedSource = active.find((source) => source.id === sourceId);
  const historicalBalance = historicalBalances[sourceId] ?? "0.00";
  const currentBalance = selectedSource?.current_balance ?? "0.00";
  const usesDevelopmentBalanceOverride = import.meta.env.DEV && selectedSource?.source_type === "INVESTOR_CONTRIBUTION";
  const available = usesDevelopmentBalanceOverride ? currentBalance : historicalBalance;
  const amountCents = amount ? decimalMoneyToCents(amount) : null;
  const availableCents = decimalMoneyToCents(available);
  const amountExceedsBalance = amountCents !== null && availableCents !== null && amountCents > availableCents;
  const valid = Boolean(sourceId && amountCents && amountCents > 0n && !amountExceedsBalance);
  return <Modal open={open} title="Adicionar fonte à Venda" description="A alocação gera o ledger na mesma transação e registra o usuário autenticado." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={() => amount && onSave({ source_id: sourceId, amount, notes: notes.trim() || null })}>{saving ? "Salvando…" : "Adicionar fonte"}</Button></>}>
    <div className="grid gap-4">
      <FormField label="Fonte"><Select value={sourceId} onChange={(event) => setSourceId(event.target.value)}>{active.map((source) => <option key={source.id} value={source.id}>{source.source_type === "REMO_CAPITAL" ? "Capital próprio REMO" : `${source.investor_name ?? "Investidor"} · ${source.contribution_code ?? "Aporte"}`}</option>)}</Select></FormField>
      <div className="grid gap-4 sm:grid-cols-2"><FormField label="Saldo na data da Venda"><Input value={formatOperationalMoney(historicalBalance)} disabled /></FormField><FormField label="Saldo atual"><Input value={formatOperationalMoney(currentBalance)} disabled /></FormField></div>
      {usesDevelopmentBalanceOverride && <p className="rounded-md border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-300"><strong>Modo de teste:</strong> esta alocação usa o saldo atual como limite, mesmo quando a Venda é anterior ao aporte. Produção continua protegida pelo saldo histórico.</p>}
      {selectedSource?.source_type === "INVESTOR_CONTRIBUTION" && <div className="grid gap-3 rounded-md border border-border/70 p-3 text-sm sm:grid-cols-3"><div><p className="text-xs text-muted-foreground">Data do aporte</p><p>{formatDate(selectedSource.contribution_date)}</p></div><div><p className="text-xs text-muted-foreground">Valor original</p><p>{formatOperationalMoney(selectedSource.original_amount)}</p></div><div><p className="text-xs text-muted-foreground">Taxa contratual</p><p>{selectedSource.monthly_rate ? formatMonthlyRate(selectedSource.monthly_rate) : "—"}</p></div></div>}
      <FormField label="Valor alocado"><Input inputMode="decimal" value={amountInput} onChange={(event) => setAmountInput(event.target.value)} placeholder="0,00" /></FormField>
      {amountExceedsBalance && <p className="text-sm text-rose-400">O valor ultrapassa o {usesDevelopmentBalanceOverride ? "saldo atual disponível para teste" : "saldo disponível na data da Venda"}.</p>}
      <FormField label="Observações"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></FormField>
    </div>
  </Modal>;
}
