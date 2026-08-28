import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export interface RefinancingFormInput { successorContractCode: string; effectiveDate: string; notes: string | null; }

export function RefinancingModal({ open, predecessorContractCode, initialSuccessorContractCode = "", correction = false, saving, onClose, onSave }: { open: boolean; predecessorContractCode: string | null; initialSuccessorContractCode?: string; correction?: boolean; saving: boolean; onClose: () => void; onSave: (input: RefinancingFormInput) => void }) {
  const [successorContractCode, setSuccessorContractCode] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  useEffect(() => { if (open) { setSuccessorContractCode(initialSuccessorContractCode); setEffectiveDate(new Date().toISOString().slice(0, 10)); setNotes(""); } }, [initialSuccessorContractCode, open]);
  const valid = successorContractCode.trim().length > 0 && effectiveDate.length === 10 && successorContractCode.trim() !== predecessorContractCode && (!correction || notes.trim().length >= 3);
  return <Modal open={open} title={correction ? "Corrigir vínculo REFIN" : "Classificar como REFIN"} description="Use REFIN somente quando o sucessor possuir nova liberação real operacional. Reprogramação sem dinheiro novo é RENEGOTIATION. A decisão não cria pagamento, allocation ou evento de ledger." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={() => onSave({ successorContractCode: successorContractCode.trim(), effectiveDate, notes: notes.trim() || null })}>{saving ? "Confirmando…" : correction ? "Salvar correção" : "Confirmar REFIN"}</Button></>}>
    <div className="space-y-4"><div className="rounded-xl border border-cyan-400/25 bg-cyan-400/5 p-4 text-sm"><strong>Contrato predecessor:</strong> {predecessorContractCode ?? "Não informado"}<p className="mt-1 text-muted-foreground">Parcelas não pagas serão classificadas como REFIN; pagamentos reais anteriores permanecem intactos.</p></div><FormField label="Código do contrato sucessor"><Input value={successorContractCode} onChange={(event) => setSuccessorContractCode(event.target.value)} placeholder="Informe o código exato" /></FormField><FormField label="Data da decisão"><Input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></FormField><FormField label="Observação" hint={correction ? "Obrigatória para a auditoria" : "Opcional"}><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={255} /></FormField></div>
  </Modal>;
}
