import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatCents, formatDate, formatDateTime, formatMoney } from "@/lib/formatters";
import { treasuryValidationPreview, treasuryValidationReady } from "@/lib/treasuryValidation";
import { treasuryApi } from "@/services/treasuryApi";
import type { TreasuryMovement, TreasuryValidationHistory } from "@/types/treasuryApi";

export function TreasuryValidationModal({ movement, onClose, onValidated }: { movement: TreasuryMovement | null; onClose: () => void; onValidated: () => void }) {
  const [amountInput, setAmountInput] = useState(""); const [observedDate, setObservedDate] = useState(""); const [bankReference, setBankReference] = useState(""); const [justification, setJustification] = useState("");
  const [history, setHistory] = useState<TreasuryValidationHistory | null>(null); const [loadingHistory, setLoadingHistory] = useState(false); const [saving, setSaving] = useState(false); const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!movement) return;
    setAmountInput(""); setObservedDate(""); setBankReference(""); setJustification(""); setError(null); setLoadingHistory(true);
    treasuryApi.getValidationHistory(movement.id).then(setHistory).catch((reason) => setError(reason instanceof Error ? reason.message : "Falha ao carregar histórico.")).finally(() => setLoadingHistory(false));
  }, [movement]);
  if (!movement) return null;
  const preview = treasuryValidationPreview(movement.amount, amountInput); const difference = preview?.differenceCents ?? null; const predictedStatus = preview?.status ?? "PENDING"; const valid = treasuryValidationReady(preview, observedDate, justification);
  const submit = async () => { if (!preview || !valid) return; setSaving(true); setError(null); try { await treasuryApi.validateMovement(movement.id, { observed_amount: preview.observedAmount, observed_date: observedDate, bank_reference: bankReference.trim() || null, justification: justification.trim() || null }); onValidated(); onClose(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao confirmar validação."); } finally { setSaving(false); } };
  return <Modal open title={movement.validation_id ? "Corrigir validação bancária" : "Validar movimento no banco"} description="A conferência cria um snapshot auditável e não altera a origem operacional." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={submit}>{saving ? "Confirmando…" : "Confirmar validação"}</Button></>}>
    <div className="space-y-5"><div className="grid gap-3 rounded-xl border bg-background/35 p-4 sm:grid-cols-2"><Info label="Tipo" value={movement.movement_type === "CONTRIBUTION" ? "Aporte" : movement.movement_type === "SALE" ? "Venda" : "Receita"} /><Info label="Referência" value={movement.reference} /><Info label="Direção" value={movement.direction === "INFLOW" ? "Entrada" : "Saída"} /><Info label="Valor esperado" value={movement.amount ? formatMoney(movement.amount) : "Indisponível"} /><Info label="Data do sistema" value={movement.movement_date ? formatDate(movement.movement_date) : "Indisponível"} /><div><p className="text-xs uppercase tracking-wider text-muted-foreground">Resultado calculado</p><div className="mt-1"><StatusBadge status={predictedStatus} /></div></div></div>
      <div className="grid gap-4 sm:grid-cols-2"><FormField label="Valor encontrado no banco"><Input inputMode="decimal" value={amountInput} onChange={(event) => setAmountInput(event.target.value)} placeholder="0,00" /></FormField><FormField label="Data encontrada no banco"><Input type="date" value={observedDate} onChange={(event) => setObservedDate(event.target.value)} /></FormField><FormField label="Referência bancária" hint="Opcional; não representa cadastro de banco."><Input value={bankReference} onChange={(event) => setBankReference(event.target.value)} maxLength={255} /></FormField><div className="rounded-xl border p-3"><p className="text-xs uppercase tracking-wider text-muted-foreground">Diferença banco − sistema</p><p className={`mt-1 text-lg font-semibold ${difference === null || difference === 0n ? "" : "text-rose-400"}`}>{difference === null ? "Informe o valor" : formatCents(difference)}</p></div><FormField label="Justificativa" hint={difference !== null && difference !== 0n ? "Obrigatória para divergência." : "Opcional quando os valores conferem."} className="sm:col-span-2"><Textarea value={justification} onChange={(event) => setJustification(event.target.value)} maxLength={4000} /></FormField></div>
      {error && <ErrorState message={error} />}
      <div><h3 className="font-semibold">Histórico de validações</h3>{loadingHistory ? <LoadingState label="Carregando histórico…" /> : history?.items.length ? <div className="mt-3 space-y-3">{history.items.map((item) => <div key={item.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-3"><span>Versão {item.version}{item.is_current ? " · atual" : ""}</span><StatusBadge status={item.status} /></div><p className="mt-2">Sistema {formatMoney(item.system_amount_snapshot)} · Banco {formatMoney(item.observed_amount)} · Diferença {formatMoney(item.difference_amount)}</p><p className="text-xs text-muted-foreground">Banco em {formatDate(item.observed_date)} · validado em {formatDateTime(item.validated_at)}{item.bank_reference ? ` · ${item.bank_reference}` : ""}</p>{item.justification && <p className="mt-1 text-xs">{item.justification}</p>}</div>)}</div> : <p className="mt-2 text-sm text-muted-foreground">Nenhuma validação anterior. O status atual é Pendente.</p>}</div>
    </div>
  </Modal>;
}

function Info({ label, value }: { label: string; value: string }) { return <div><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 font-medium">{value}</p></div>; }
