import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { FundingInvestor, FundingInvestorInput, InvestorStatus } from "@/types/fundingApi";

const emptyInput: FundingInvestorInput = { name: "", tax_id: null, phone: null, status: "ACTIVE", notes: null };

function documentMask(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 14);
  if (digits.length <= 11) return digits.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
  return digits.replace(/(\d{2})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}

function phoneMask(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  return digits.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d{4})$/, "$1-$2");
}

export function InvestorFormModal({ open, investor, saving = false, onClose, onSave }: { open: boolean; investor?: FundingInvestor; saving?: boolean; onClose: () => void; onSave: (input: FundingInvestorInput) => void }) {
  const [form, setForm] = useState<FundingInvestorInput>(emptyInput);
  useEffect(() => setForm(investor ? { name: investor.name, phone: investor.phone, status: investor.status, notes: investor.notes } : emptyInput), [investor, open]);
  const valid = form.name.trim().length >= 3;
  const submit = () => {
    const input = { ...form, name: form.name.trim(), phone: form.phone?.trim() || null };
    if (investor && !form.tax_id) delete input.tax_id;
    onSave(input);
  };
  return <Modal open={open} title={investor ? "Editar investidor" : "Novo investidor"} description="Dados cadastrais reais; o documento é mascarado nas respostas da API." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={submit}>{saving ? "Salvando…" : "Salvar investidor"}</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary sm:col-span-2">Dados cadastrais</p>
      <FormField label="Nome completo ou razão social" className="sm:col-span-2"><Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></FormField>
      <FormField label="CPF ou CNPJ" hint={investor?.tax_id_masked ? `Atual: ${investor.tax_id_masked}. Deixe vazio para manter.` : undefined}><Input inputMode="numeric" value={form.tax_id ?? ""} onChange={(event) => setForm((current) => ({ ...current, tax_id: documentMask(event.target.value) || null }))} /></FormField>
      <FormField label="Telefone com DDD"><Input inputMode="tel" value={form.phone ?? ""} onChange={(event) => setForm((current) => ({ ...current, phone: phoneMask(event.target.value) || null }))} /></FormField>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary sm:col-span-2">Situação</p>
      <FormField label="Status"><Select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as InvestorStatus }))}><option value="ACTIVE">Ativo</option><option value="INACTIVE">Inativo</option></Select></FormField>
      <FormField label="Observação" className="sm:col-span-2"><Textarea value={form.notes ?? ""} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value || null }))} /></FormField>
    </div>
  </Modal>;
}
