import { useEffect, useState } from "react";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { PaymentBatchInput } from "@/types/funding";

export function PaymentConfirmationModal({ open, remunerationIds, onClose, onConfirm }: { open: boolean; remunerationIds: string[]; onClose: () => void; onConfirm: (input: PaymentBatchInput) => void }) {
  const [date, setDate] = useState("2026-07-31"); const [cashAccount, setCashAccount] = useState("Conta Caixa Demo 01"); const [owner, setOwner] = useState("Tesouraria Demo"); const [notes, setNotes] = useState("");
  useEffect(() => { if (open) setNotes(""); }, [open]);
  return <Modal open={open} title="Confirmar pagamento de remuneração" description="Será criada uma saída real de tesouraria e registrada a conta fictícia utilizada." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!remunerationIds.length || !date || !owner} onClick={() => onConfirm({ remunerationIds, date, cashAccount, owner, notes })}>Confirmar pagamento</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2"><FormField label="Data"><Input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></FormField><FormField label="Conta de saída"><Select value={cashAccount} onChange={(event) => setCashAccount(event.target.value)}><option>Conta Caixa Demo 01</option><option>Conta Caixa Demo 02</option></Select></FormField><FormField label="Responsável" className="sm:col-span-2"><Input value={owner} onChange={(event) => setOwner(event.target.value)} /></FormField><FormField label="Observação" className="sm:col-span-2"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></FormField></div>
  </Modal>;
}
