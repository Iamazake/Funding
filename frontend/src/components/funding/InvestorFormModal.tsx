import { useEffect, useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { Investor, InvestorInput, InvestorStatus, RiskGrade } from "@/types/funding";

const emptyInput: InvestorInput = {
  name: "", personType: "PF", maskedDocument: "000.***.***-00", riskGrade: "MEDIO",
  contractSigned: false, signedAt: null, paymentDay: 10, status: "PENDENTE",
  contacts: [{ label: "E-mail", value: "" }, { label: "Telefone", value: "(00) 90000-0000" }],
  bankAccount: { bank: "Banco Fictício", branchMasked: "****", accountMasked: "*****-**", pixMasked: "***@demo.invalid" },
  notes: "",
};

function fromInvestor(investor?: Investor): InvestorInput {
  if (!investor) return emptyInput;
  return {
    name: investor.name, personType: investor.personType,
    maskedDocument: investor.maskedDocument, riskGrade: investor.riskGrade,
    contractSigned: investor.contractSigned, signedAt: investor.signedAt, paymentDay: investor.paymentDay,
    status: investor.status, contacts: structuredClone(investor.contacts), bankAccount: structuredClone(investor.bankAccount),
    notes: investor.notes,
  };
}

export function InvestorFormModal({ open, investor, onClose, onSave }: { open: boolean; investor?: Investor; onClose: () => void; onSave: (input: InvestorInput) => void }) {
  const [form, setForm] = useState<InvestorInput>(() => fromInvestor(investor));
  useEffect(() => setForm(fromInvestor(investor)), [investor, open]);
  const update = <K extends keyof InvestorInput>(field: K, value: InvestorInput[K]) => setForm((current) => ({ ...current, [field]: value }));
  const updateContact = (index: number, value: string) => update("contacts", form.contacts.map((contact, contactIndex) => contactIndex === index ? { ...contact, value } : contact));
  const valid = form.name.trim().length >= 3 && form.paymentDay >= 1 && form.paymentDay <= 31 && form.contacts[0]?.value.includes("@");
  return <Modal open={open} title={investor ? "Editar investidor" : "Novo investidor"} description="Documentos, contatos e conta bancária devem permanecer mascarados e fictícios." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid} onClick={() => onSave(form)}>Salvar investidor</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Nome fictício" className="sm:col-span-2"><Input value={form.name} onChange={(event) => update("name", event.target.value)} /></FormField>
      <FormField label="Tipo"><Select value={form.personType} onChange={(event) => update("personType", event.target.value as InvestorInput["personType"])}><option value="PF">Pessoa física</option><option value="PJ">Pessoa jurídica</option></Select></FormField>
      <FormField label="Documento mascarado"><Input value={form.maskedDocument} onChange={(event) => update("maskedDocument", event.target.value)} /></FormField>
      <FormField label="Grau de risco"><Select value={form.riskGrade} onChange={(event) => update("riskGrade", event.target.value as RiskGrade)}><option value="BAIXO">Baixo</option><option value="MEDIO">Médio</option><option value="ALTO">Alto</option></Select></FormField>
      <FormField label="Status"><Select value={form.status} onChange={(event) => update("status", event.target.value as InvestorStatus)}><option value="PENDENTE">Pendente</option><option value="ATIVO">Ativo</option><option value="INATIVO">Inativo</option><option value="ENCERRADO">Encerrado</option></Select></FormField>
      <FormField label="Contrato assinado"><Select value={form.contractSigned ? "yes" : "no"} onChange={(event) => update("contractSigned", event.target.value === "yes")}><option value="no">Não</option><option value="yes">Sim</option></Select></FormField>
      <FormField label="Data da assinatura"><Input type="date" value={form.signedAt ?? ""} onChange={(event) => update("signedAt", event.target.value || null)} /></FormField>
      <FormField label="Dia de pagamento"><Input type="number" min={1} max={31} value={form.paymentDay} onChange={(event) => update("paymentDay", Number.parseInt(event.target.value, 10) || 1)} /></FormField>
      <FormField label="E-mail fictício"><Input type="email" value={form.contacts[0]?.value ?? ""} onChange={(event) => updateContact(0, event.target.value)} /></FormField>
      <FormField label="Telefone fictício"><Input value={form.contacts[1]?.value ?? ""} onChange={(event) => updateContact(1, event.target.value)} /></FormField>
      <FormField label="Banco fictício"><Input value={form.bankAccount.bank} onChange={(event) => update("bankAccount", { ...form.bankAccount, bank: event.target.value })} /></FormField>
      <FormField label="Agência mascarada"><Input value={form.bankAccount.branchMasked} onChange={(event) => update("bankAccount", { ...form.bankAccount, branchMasked: event.target.value })} /></FormField>
      <FormField label="Conta mascarada"><Input value={form.bankAccount.accountMasked} onChange={(event) => update("bankAccount", { ...form.bankAccount, accountMasked: event.target.value })} /></FormField>
      <FormField label="PIX mascarado"><Input value={form.bankAccount.pixMasked} onChange={(event) => update("bankAccount", { ...form.bankAccount, pixMasked: event.target.value })} /></FormField>
      <FormField label="Observações" className="sm:col-span-2"><Textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} /></FormField>
    </div>
  </Modal>;
}
