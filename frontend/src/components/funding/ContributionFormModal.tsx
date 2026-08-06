import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { currencyInputToCents, formatCentsAmount } from "@/lib/formatters";
import { calculateCapitalRemuneration } from "@/repositories/fundingRepository";
import type { Contribution, ContributionInput, ContributionStatus, Investor } from "@/types/funding";

interface FormState { investorId: string; originalAmount: string; availableBalance: string; allocatedBalance: string; startDate: string; endDate: string; monthlyRateBps: string; status: ContributionStatus; notes: string; }

function initial(item: Contribution | undefined, investors: Investor[], presetInvestorId?: string): FormState {
  if (item) return { investorId: item.investorId, originalAmount: formatCentsAmount(item.originalAmount), availableBalance: formatCentsAmount(item.availableBalance), allocatedBalance: formatCentsAmount(item.allocatedBalance), startDate: item.startDate, endDate: item.endDate, monthlyRateBps: String(item.monthlyRateBps), status: item.status, notes: item.notes };
  return { investorId: presetInvestorId ?? investors[0]?.id ?? "", originalAmount: "", availableBalance: "", allocatedBalance: "0,00", startDate: "2026-07-31", endDate: "2027-07-31", monthlyRateBps: "200", status: "ATIVO", notes: "" };
}

export function ContributionFormModal({ open, contribution, investors, presetInvestorId, onClose, onSave }: { open: boolean; contribution?: Contribution; investors: Investor[]; presetInvestorId?: string; onClose: () => void; onSave: (input: ContributionInput) => void }) {
  const [form, setForm] = useState(() => initial(contribution, investors, presetInvestorId));
  useEffect(() => setForm(initial(contribution, investors, presetInvestorId)), [contribution, investors, presetInvestorId, open]);
  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((current) => ({ ...current, [key]: value }));
  const original = currencyInputToCents(form.originalAmount); const available = currencyInputToCents(form.availableBalance || form.originalAmount); const allocated = currencyInputToCents(form.allocatedBalance);
  const rate = Number.parseInt(form.monthlyRateBps, 10); const validRate = Number.isInteger(rate) && rate >= 0;
  const valid = Boolean(form.investorId && original && centsPositive(original) && available !== null && allocated !== null && validRate && form.startDate && form.endDate >= form.startDate && BigInt(available ?? "0") + BigInt(allocated ?? "0") <= BigInt(original ?? "0"));
  const expected = original !== null && validRate ? calculateCapitalRemuneration(original, rate) : "0";
  const submit = () => { if (!valid || original === null || available === null || allocated === null) return; onSave({ investorId: form.investorId, originalAmount: original, availableBalance: available, allocatedBalance: allocated, startDate: form.startDate, endDate: form.endDate, monthlyRateBps: rate, status: form.status, notes: form.notes }); };
  return <Modal open={open} title={contribution ? `Editar ${contribution.code}` : "Novo aporte"} description="Taxa em basis points; remuneração calculada sobre o valor originalmente aportado." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid} onClick={submit}>Salvar aporte</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Investidor" className="sm:col-span-2"><Select className="w-full" value={form.investorId} onChange={(event) => update("investorId", event.target.value)}>{investors.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</Select></FormField>
      <FormField label="Valor originalmente aportado"><Input inputMode="decimal" value={form.originalAmount} onChange={(event) => { update("originalAmount", event.target.value); if (!contribution) update("availableBalance", event.target.value); }} /></FormField>
      <FormField label="Taxa mensal (basis points)" hint="2% = 200 bps"><Input inputMode="numeric" value={form.monthlyRateBps} onChange={(event) => update("monthlyRateBps", event.target.value.replace(/\D/g, ""))} /></FormField>
      <FormField label="Remuneração mensal calculada"><Input value={formatCentsAmount(expected)} disabled /></FormField>
      <FormField label="Base de cálculo"><Input value="Valor originalmente aportado" disabled /></FormField>
      <FormField label="Saldo disponível"><Input inputMode="decimal" value={form.availableBalance} onChange={(event) => update("availableBalance", event.target.value)} /></FormField>
      <FormField label="Saldo alocado"><Input inputMode="decimal" value={form.allocatedBalance} onChange={(event) => update("allocatedBalance", event.target.value)} /></FormField>
      <FormField label="Data inicial"><Input type="date" value={form.startDate} onChange={(event) => update("startDate", event.target.value)} /></FormField>
      <FormField label="Data final"><Input type="date" value={form.endDate} onChange={(event) => update("endDate", event.target.value)} /></FormField>
      <FormField label="Status"><Select value={form.status} onChange={(event) => update("status", event.target.value as ContributionStatus)}>{["PENDENTE", "ATIVO", "PARCIALMENTE_ALOCADO", "TOTALMENTE_ALOCADO", "EM_LIQUIDACAO", "LIQUIDADO", "LIQUIDADO_ANTECIPADAMENTE", "CANCELADO"].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</Select></FormField>
      <FormField label="Observações" className="sm:col-span-2"><Textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} /></FormField>
    </div>
  </Modal>;
}

function centsPositive(value: string): boolean { return BigInt(value) > 0n; }
