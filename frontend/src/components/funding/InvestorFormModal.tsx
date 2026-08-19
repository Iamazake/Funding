import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { FundingInvestor, FundingInvestorInput, InvestorStatus } from "@/types/fundingApi";

const emptyInput: FundingInvestorInput = { name: "", status: "ACTIVE", notes: null };

export function InvestorFormModal({ open, investor, saving = false, onClose, onSave }: { open: boolean; investor?: FundingInvestor; saving?: boolean; onClose: () => void; onSave: (input: FundingInvestorInput) => void }) {
  const [form, setForm] = useState<FundingInvestorInput>(emptyInput);
  useEffect(() => setForm(investor ? { name: investor.name, status: investor.status, notes: investor.notes } : emptyInput), [investor, open]);
  const valid = form.name.trim().length >= 3;
  return <Modal open={open} title={investor ? "Editar investidor" : "Novo investidor"} description="Cadastro real persistido no Supabase pela API." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={() => onSave({ ...form, name: form.name.trim() })}>{saving ? "Salvando…" : "Salvar investidor"}</Button></>}>
    <div className="grid gap-4">
      <FormField label="Nome"><Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></FormField>
      <FormField label="Status"><Select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as InvestorStatus }))}><option value="ACTIVE">Ativo</option><option value="INACTIVE">Inativo</option></Select></FormField>
      <FormField label="Observações"><Textarea value={form.notes ?? ""} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value || null }))} /></FormField>
    </div>
  </Modal>;
}
