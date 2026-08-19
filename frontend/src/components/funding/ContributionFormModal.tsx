import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { brazilianMoneyToDecimal, decimalToBrazilianInput } from "@/lib/fundingFormat";
import type { ContributionStatus, FundingContribution, FundingContributionInput, FundingInvestor } from "@/types/fundingApi";

interface FormState { investor_id: string; contribution_date: string; original_amount: string; monthly_rate: string; status: ContributionStatus; notes: string; }

function initial(item: FundingContribution | undefined, investors: FundingInvestor[], presetInvestorId?: string): FormState {
  if (item) return { investor_id: item.investor_id, contribution_date: item.contribution_date, original_amount: decimalToBrazilianInput(item.original_amount), monthly_rate: item.monthly_rate.replace(".", ","), status: item.status, notes: item.notes ?? "" };
  return { investor_id: presetInvestorId ?? investors[0]?.id ?? "", contribution_date: new Date().toISOString().slice(0, 10), original_amount: "", monthly_rate: "0,02", status: "ACTIVE", notes: "" };
}

export function ContributionFormModal({ open, contribution, investors, presetInvestorId, saving = false, onClose, onSave }: { open: boolean; contribution?: FundingContribution; investors: FundingInvestor[]; presetInvestorId?: string; saving?: boolean; onClose: () => void; onSave: (input: FundingContributionInput) => void }) {
  const [form, setForm] = useState(() => initial(contribution, investors, presetInvestorId));
  useEffect(() => setForm(initial(contribution, investors, presetInvestorId)), [contribution, investors, presetInvestorId, open]);
  const amount = brazilianMoneyToDecimal(form.original_amount);
  const rate = form.monthly_rate.trim().replace(",", ".");
  const validRate = /^0(\.\d{1,10})?$|^1(\.0{1,10})?$/.test(rate);
  const valid = Boolean(form.investor_id && form.contribution_date && amount && BigInt(amount.replace(".", "")) > 0n && validRate);
  const submit = () => { if (valid && amount) onSave({ investor_id: form.investor_id, contribution_date: form.contribution_date, original_amount: amount, monthly_rate: rate, status: form.status, notes: form.notes || null }); };
  return <Modal open={open} title={contribution ? `Editar ${contribution.code}` : "Novo aporte"} description="Taxa armazenada como fração decimal: 2% a.m. = 0,02. O valor original fica auditado." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={submit}>{saving ? "Salvando…" : "Salvar aporte"}</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Investidor" className="sm:col-span-2"><Select value={form.investor_id} onChange={(event) => setForm((current) => ({ ...current, investor_id: event.target.value }))}>{investors.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</Select></FormField>
      <FormField label="Valor original"><Input inputMode="decimal" value={form.original_amount} disabled={Boolean(contribution && !contribution.original_amount_editable)} onChange={(event) => setForm((current) => ({ ...current, original_amount: event.target.value }))} /></FormField>
      <FormField label="Taxa mensal (fração)" hint="2% = 0,02"><Input inputMode="decimal" value={form.monthly_rate} onChange={(event) => setForm((current) => ({ ...current, monthly_rate: event.target.value }))} /></FormField>
      <FormField label="Data do aporte"><Input type="date" value={form.contribution_date} onChange={(event) => setForm((current) => ({ ...current, contribution_date: event.target.value }))} /></FormField>
      <FormField label="Status"><Select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as ContributionStatus }))}><option value="ACTIVE">Ativo</option><option value="INACTIVE">Inativo</option><option value="CLOSED">Encerrado</option></Select></FormField>
      <FormField label="Observações" className="sm:col-span-2"><Textarea value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} /></FormField>
    </div>
  </Modal>;
}
