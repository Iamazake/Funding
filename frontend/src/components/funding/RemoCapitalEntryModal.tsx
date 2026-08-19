import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { brazilianMoneyToDecimal } from "@/lib/fundingFormat";

export interface RemoCapitalInput {
  amount: string;
  effective_date: string;
  direction: "CREDIT" | "DEBIT";
  notes: string;
}

export function RemoCapitalEntryModal({ open, saving, onClose, onSave }: { open: boolean; saving: boolean; onClose: () => void; onSave: (input: RemoCapitalInput) => void }) {
  const [amountInput, setAmountInput] = useState(""); const [effectiveDate, setEffectiveDate] = useState(""); const [direction, setDirection] = useState<"CREDIT" | "DEBIT">("CREDIT"); const [notes, setNotes] = useState("");
  useEffect(() => { if (open) { setAmountInput(""); setEffectiveDate(new Date().toISOString().slice(0, 10)); setDirection("CREDIT"); setNotes(""); } }, [open]);
  const amount = brazilianMoneyToDecimal(amountInput); const valid = Boolean(amount && effectiveDate && notes.trim().length >= 3);
  return <Modal open={open} title="Registrar capital próprio REMO" description="Movimentação administrativa explícita e auditada com o usuário autenticado." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={() => amount && onSave({ amount, effective_date: effectiveDate, direction, notes: notes.trim() })}>{saving ? "Registrando…" : "Registrar movimentação"}</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2"><FormField label="Direção"><Select value={direction} onChange={(event) => setDirection(event.target.value as "CREDIT" | "DEBIT")}><option value="CREDIT">Entrada</option><option value="DEBIT">Saída / ajuste redutor</option></Select></FormField><FormField label="Data efetiva"><Input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></FormField><FormField label="Valor"><Input inputMode="decimal" value={amountInput} onChange={(event) => setAmountInput(event.target.value)} placeholder="0,00" /></FormField><FormField label="Justificativa" className="sm:col-span-2"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></FormField></div>
  </Modal>;
}
