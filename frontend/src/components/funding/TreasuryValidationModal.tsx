import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import {
  centsToMoney,
  formatCents,
  formatDate,
  formatDateTime,
  formatMoney,
  parseBrazilianMoneyToCents,
} from "@/lib/formatters";
import { treasuryValidationPreview, treasuryValidationReady } from "@/lib/treasuryValidation";
import { debtContinuityApi } from "@/services/debtContinuityApi";
import { getSale, getSales } from "@/services/operationalApi";
import { treasuryApi } from "@/services/treasuryApi";
import type { SaleItem } from "@/types/operational";
import type { TreasuryBankCode, TreasuryMovement, TreasuryValidationHistory } from "@/types/treasuryApi";

const bankLabels: Record<TreasuryBankCode, string> = {
  INTER: "Banco Inter",
  BTG: "Banco BTG",
  PICPAY: "PicPay",
  NUBANK: "Nubank",
  C6: "C6 Bank",
  CASH: "Dinheiro",
};

type OperationType = "NORMAL" | "REFINANCING" | "RENEGOTIATION";

interface EconomicValues {
  originalPrincipal: string;
  principalPaid: string;
  principalRolled: string;
  interestPaid: string;
}

export function TreasuryValidationModal({
  movement,
  onClose,
  onValidated,
}: {
  movement: TreasuryMovement | null;
  onClose: () => void;
  onValidated: () => void;
}) {
  const { user } = useAuth();
  const [operationType, setOperationType] = useState<OperationType>("NORMAL");
  const [amountInput, setAmountInput] = useState("");
  const [observedDate, setObservedDate] = useState("");
  const [bankCode, setBankCode] = useState<TreasuryBankCode | "">("");
  const [justification, setJustification] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [continuityNotes, setContinuityNotes] = useState("");
  const [predecessorQuery, setPredecessorQuery] = useState("");
  const [predecessors, setPredecessors] = useState<SaleItem[]>([]);
  const [predecessorIds, setPredecessorIds] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const [originalPrincipal, setOriginalPrincipal] = useState("");
  const [principalPaid, setPrincipalPaid] = useState("");
  const [principalRolled, setPrincipalRolled] = useState("");
  const [interestPaid, setInterestPaid] = useState("");
  const [history, setHistory] = useState<TreasuryValidationHistory | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [canonicalSale, setCanonicalSale] = useState<SaleItem | null>(null);
  const [loadingSale, setLoadingSale] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canonicalSaleId = movement?.sale_id
    ?? (movement?.movement_type === "SALE" && movement.id.startsWith("sale:") ? movement.id : null);

  useEffect(() => {
    if (!movement) return;
    setOperationType(operationTypeFromContinuity(movement.continuity_type));
    setAmountInput("");
    setObservedDate("");
    setBankCode("");
    setJustification("");
    setEffectiveDate(new Date().toISOString().slice(0, 10));
    setContinuityNotes("");
    setPredecessorQuery("");
    setPredecessors([]);
    setPredecessorIds([]);
    setOriginalPrincipal("");
    setPrincipalPaid("");
    setPrincipalRolled("");
    setInterestPaid("");
    setCanonicalSale(null);
    setError(null);
    setLoadingHistory(true);
    treasuryApi.getValidationHistory(movement.id)
      .then(setHistory)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Falha ao carregar histórico."))
      .finally(() => setLoadingHistory(false));
    if (canonicalSaleId) {
      setLoadingSale(true);
      getSale(canonicalSaleId)
        .then((sale) => {
          setCanonicalSale(sale);
          setOperationType(operationTypeFromContinuity(sale.continuity_type));
        })
        .catch((reason) => setError(reason instanceof Error ? reason.message : "Falha ao carregar a venda canônica."))
        .finally(() => setLoadingSale(false));
    } else {
      setLoadingSale(false);
    }
  }, [canonicalSaleId, movement]);

  const preview = movement
    ? treasuryValidationPreview(movement.amount, amountInput)
    : null;
  const difference = preview?.differenceCents ?? null;
  const bankReady = treasuryValidationReady(preview, observedDate, justification);
  const successorIdentity = canonicalSaleId?.slice("sale:".length) ?? null;
  const selectedPredecessors = predecessors.filter((item) => predecessorIds.includes(item.id));
  const economicValues = useMemo(
    () => parseEconomicValues({ originalPrincipal, principalPaid, principalRolled, interestPaid }),
    [interestPaid, originalPrincipal, principalPaid, principalRolled],
  );
  const successorReleasedAmount = canonicalSale?.released_amount ?? movement?.released_amount ?? null;
  const positiveRelease = Boolean(successorReleasedAmount && Number(successorReleasedAmount) > 0);
  const isSale = movement?.movement_type === "SALE";
  const isRevenue = movement?.movement_type === "REVENUE";
  const hasConfirmedContinuity = Boolean(
    canonicalSale?.continuity_id || canonicalSale?.continuity_type || movement?.continuity_type,
  );
  const canClassify = Boolean((isSale || isRevenue) && canonicalSaleId && user?.role === "ADMIN");
  const clientsMatch = Boolean(
    canonicalSale?.client_identity_id
    && selectedPredecessors.length === predecessorIds.length
    && selectedPredecessors.every(
      (item) => item.client_identity_id === canonicalSale.client_identity_id,
    ),
  );
  const continuityReady = Boolean(
    successorIdentity
    && predecessorIds.length > 0
    && !predecessorIds.includes(canonicalSaleId ?? "")
    && clientsMatch
    && effectiveDate,
  );
  const bankAction = operationType === "NORMAL" || hasConfirmedContinuity || (isSale && operationType === "REFINANCING");
  const valid = hasConfirmedContinuity || operationType === "NORMAL"
    ? bankReady
    : operationType === "REFINANCING"
      ? continuityReady && positiveRelease && (isRevenue || bankReady)
      : continuityReady
        && Boolean(movement?.source_batch_id)
        && continuityNotes.trim().length >= 3
        && economicValues !== null;

  if (!movement) return null;

  const searchPredecessors = async () => {
    if (!predecessorQuery.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const response = await getSales({
        page: 1,
        page_size: 25,
        contract: predecessorQuery.trim(),
        sort_by: "operation_date",
        sort_order: "desc",
      });
      const candidates = response.items.filter((item) => item.id !== canonicalSaleId);
      setPredecessors((current) => [
        ...current,
        ...candidates.filter((candidate) => !current.some((item) => item.id === candidate.id)),
      ]);
      if (candidates.length === 0) setError("Nenhum contrato predecessor foi encontrado.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao buscar predecessor.");
    } finally {
      setSearching(false);
    }
  };

  const submit = async () => {
    if (!valid || (bankAction && !preview)) return;
    setSaving(true);
    setError(null);
    try {
      if (operationType === "NORMAL" || hasConfirmedContinuity) {
        await validateBankMovement(movement, preview!, observedDate, bankCode, justification);
      } else if (operationType === "REFINANCING") {
        if (isSale) {
          await validateBankMovement(movement, preview!, observedDate, bankCode, justification);
        }
        await debtContinuityApi.createRefinancing({
          predecessor_sale_identity_ids: predecessorIds.map((value) => value.replace(/^sale:/, "")),
          successor_sale_identity_id: successorIdentity!,
          effective_date: effectiveDate,
          notes: continuityNotes.trim() || null,
          principal_rolled: null,
        });
      } else {
        const review = await debtContinuityApi.createRenegotiationReview({
          source_batch_id: movement.source_batch_id!,
          successor_sale_identity_id: successorIdentity!,
          candidate_predecessor_sale_identity_ids: predecessorIds.map((value) => value.replace(/^sale:/, "")),
          continuity_type: "RENEGOTIATION",
          scope: "NEW_CONTRACT",
          effective_date: effectiveDate,
          reason: continuityNotes.trim(),
          evidence: { cockpit: "TREASURY_BANK_VALIDATION", movement_key: movement.id },
        });
        await debtContinuityApi.confirmRenegotiation(review.id, {
          predecessor_sale_identity_ids: predecessorIds.map((value) => value.replace(/^sale:/, "")),
          original_principal: economicValues!.originalPrincipal,
          principal_paid: economicValues!.principalPaid,
          principal_rolled: economicValues!.principalRolled,
          interest_paid: economicValues!.interestPaid,
          has_new_disbursement: false,
          effective_date: effectiveDate,
          evidence: { cockpit: "TREASURY_BANK_VALIDATION", movement_key: movement.id },
        });
      }
      onValidated();
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao confirmar a operação.");
    } finally {
      setSaving(false);
    }
  };

  const predictedStatus = preview?.status ?? "PENDING";
  const submitLabel = saving
    ? "Confirmando…"
    : hasConfirmedContinuity || operationType === "NORMAL"
      ? "Confirmar validação"
      : operationType === "REFINANCING"
        ? isSale ? "Validar banco e confirmar REFIN" : "Confirmar REFIN"
        : "Confirmar RENEGOCIAÇÃO";

  return (
    <Modal
      open
      title={movement.validation_id ? "Revisar operação e validação" : "Classificar e validar operação"}
      description="Cockpit operacional para validação bancária e continuidade da dívida, com auditorias independentes."
      onClose={onClose}
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!valid || saving} onClick={submit}>{submitLabel}</Button></>}
    >
      <div className="space-y-5">
        {(isSale || isRevenue) && (
          <FormField
            label="Tipo da operação"
            hint={hasConfirmedContinuity
              ? "Classificação canônica já confirmada e compartilhada com Vendas."
              : !canonicalSaleId
                ? "Receita sem venda canônica resolvida; a validação bancária continua disponível."
                : !canClassify
                  ? "Somente administradores classificam REFIN ou RENEGOCIAÇÃO."
                  : undefined}
          >
            <Select value={operationType} disabled={!canClassify || hasConfirmedContinuity || loadingSale} onChange={(event) => setOperationType(event.target.value as OperationType)}>
              <option value="NORMAL">NORMAL</option>
              <option value="REFINANCING">REFINANCIAMENTO</option>
              <option value="RENEGOTIATION">RENEGOCIAÇÃO</option>
            </Select>
          </FormField>
        )}

        {loadingSale && <LoadingState label="Carregando venda canônica…" />}
        {hasConfirmedContinuity && (
          <ConfirmedContinuity sale={canonicalSale} movement={movement} />
        )}

        <MovementSummary
          movement={movement}
          predictedStatus={predictedStatus}
          successorReleasedAmount={successorReleasedAmount}
        />

        {operationType !== "NORMAL" && !hasConfirmedContinuity && (
          <ContinuityFields
            movement={movement}
            operationType={operationType}
            query={predecessorQuery}
            setQuery={setPredecessorQuery}
            searching={searching}
            search={searchPredecessors}
            predecessors={predecessors}
            predecessorIds={predecessorIds}
            setPredecessorIds={setPredecessorIds}
            successorClientIdentityId={canonicalSale?.client_identity_id ?? null}
            effectiveDate={effectiveDate}
            setEffectiveDate={setEffectiveDate}
            notes={continuityNotes}
            setNotes={setContinuityNotes}
          />
        )}

        {operationType === "RENEGOTIATION" && !hasConfirmedContinuity ? (
          <RenegotiationEconomics
            values={{ originalPrincipal, principalPaid, principalRolled, interestPaid }}
            setters={{ setOriginalPrincipal, setPrincipalPaid, setPrincipalRolled, setInterestPaid }}
            valid={economicValues !== null}
          />
        ) : bankAction ? (
          <BankFields
            amountInput={amountInput}
            setAmountInput={setAmountInput}
            observedDate={observedDate}
            setObservedDate={setObservedDate}
            bankCode={bankCode}
            setBankCode={setBankCode}
            justification={justification}
            setJustification={setJustification}
            difference={difference}
          />
        ) : (
          <div className="rounded-xl border border-cyan-400/25 bg-cyan-400/5 p-4 text-sm">
            A classificação da continuidade não valida este recebimento no banco. A entrada real permanece independente e poderá ser validada separadamente.
          </div>
        )}

        {operationType === "REFINANCING" && !hasConfirmedContinuity && !positiveRelease && (
          <ErrorState message="REFIN exige released_amount operacional maior que zero; o valor não é calculado por diferença entre contratos." />
        )}
        {operationType === "RENEGOTIATION" && !hasConfirmedContinuity && (
          <div className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-4 text-sm">
            RENEGOCIAÇÃO registra somente continuidade da dívida. Nenhuma validação bancária de R$ 0, allocation, ledger ou saída será criada.
          </div>
        )}
        {error && <ErrorState message={error} />}
        {bankAction && <ValidationHistory history={history} loading={loadingHistory} />}
      </div>
    </Modal>
  );
}

async function validateBankMovement(
  movement: TreasuryMovement,
  preview: NonNullable<ReturnType<typeof treasuryValidationPreview>>,
  observedDate: string,
  bankCode: TreasuryBankCode | "",
  justification: string,
) {
  await treasuryApi.validateMovement(movement.id, {
    observed_amount: preview.observedAmount,
    observed_date: observedDate,
    bank_reference: null,
    bank_code: bankCode || null,
    justification: justification.trim() || null,
  });
}

function ConfirmedContinuity({ sale, movement }: { sale: SaleItem | null; movement: TreasuryMovement }) {
  const continuityType = sale?.continuity_type ?? movement.continuity_type ?? null;
  const continuityRole = sale?.continuity_role ?? movement.continuity_role ?? null;
  const linkedContracts = continuityRole === "PREDECESSOR"
    ? [sale?.successor_contract_code].filter(Boolean)
    : sale?.predecessor_contract_codes?.length
      ? sale.predecessor_contract_codes
      : [sale?.predecessor_contract_code].filter(Boolean);
  return (
    <div className="rounded-xl border border-emerald-400/25 bg-emerald-400/5 p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">Continuidade canônica confirmada</p>
        <StatusBadge status={operationTypeLabel(continuityType)} />
      </div>
      <div className="mt-3 grid gap-2 text-muted-foreground sm:grid-cols-3">
        <span>Papel: {continuityRole === "PREDECESSOR" ? "predecessor" : continuityRole === "SUCCESSOR" ? "sucessor" : "não informado"}</span>
        <span>Contratos relacionados: {linkedContracts.length ? linkedContracts.join(", ") : "não informados"}</span>
        <span>Data efetiva: {sale?.continuity_effective_date ? formatDate(sale.continuity_effective_date) : "não informada"}</span>
      </div>
      {sale?.continuity_notes && <p className="mt-2 text-muted-foreground">{sale.continuity_notes}</p>}
      <p className="mt-3">Esta classificação pertence à venda canônica e é a mesma exibida em Vendas e Receita. A validação bancária deste movimento permanece independente.</p>
    </div>
  );
}

function MovementSummary({
  movement,
  predictedStatus,
  successorReleasedAmount,
}: {
  movement: TreasuryMovement;
  predictedStatus: string;
  successorReleasedAmount: string | null;
}) {
  const isRevenue = movement.movement_type === "REVENUE";
  return (
    <div className="grid gap-3 rounded-xl border bg-background/35 p-4 sm:grid-cols-2">
      <Info label="Movimento" value={movement.movement_type === "CONTRIBUTION" ? "Aporte" : movement.movement_type === "SALE" ? "Venda" : "Receita"} />
      <Info label="Direção" value={movement.direction === "INFLOW" ? "Entrada" : "Saída"} />
      <Info label="Contrato atual / sucessor" value={movement.contract_code ?? "Não informado"} />
      <Info label={isRevenue ? "Recebimento desta parcela" : "Valor do movimento bancário"} value={movement.amount ? formatMoney(movement.amount) : "Indisponível"} />
      <Info label="Released amount do contrato sucessor" value={successorReleasedAmount ? formatMoney(successorReleasedAmount) : "Indisponível"} />
      <Info label="Data do sistema" value={movement.movement_date ? formatDate(movement.movement_date) : "Indisponível"} />
      <div><p className="text-xs uppercase tracking-wider text-muted-foreground">Resultado bancário</p><div className="mt-1"><StatusBadge status={predictedStatus} /></div></div>
    </div>
  );
}

function operationTypeFromContinuity(
  continuityType: TreasuryMovement["continuity_type"] | SaleItem["continuity_type"],
): OperationType {
  if (continuityType === "REFINANCING") return "REFINANCING";
  if (continuityType === "RENEGOTIATION" || continuityType === "ROLLOVER") return "RENEGOTIATION";
  return "NORMAL";
}

function operationTypeLabel(
  continuityType: TreasuryMovement["continuity_type"] | SaleItem["continuity_type"],
) {
  if (continuityType === "REFINANCING") return "REFIN";
  if (continuityType === "RENEGOTIATION" || continuityType === "ROLLOVER") return "RENEG";
  return "NORMAL";
}

function ContinuityFields({
  movement, operationType, query, setQuery, searching, search, predecessors,
  predecessorIds, setPredecessorIds, successorClientIdentityId,
  effectiveDate, setEffectiveDate, notes, setNotes,
}: {
  movement: TreasuryMovement;
  operationType: Exclude<OperationType, "NORMAL">;
  query: string;
  setQuery: (value: string) => void;
  searching: boolean;
  search: () => void;
  predecessors: SaleItem[];
  predecessorIds: string[];
  setPredecessorIds: (value: string[]) => void;
  successorClientIdentityId: number | null;
  effectiveDate: string;
  setEffectiveDate: (value: string) => void;
  notes: string;
  setNotes: (value: string) => void;
}) {
  const selected = predecessors.filter((item) => predecessorIds.includes(item.id));
  const toggle = (item: SaleItem) => {
    if (predecessorIds.includes(item.id)) {
      setPredecessorIds(predecessorIds.filter((value) => value !== item.id));
      return;
    }
    if (
      successorClientIdentityId === null
      || item.client_identity_id === null
      || item.client_identity_id === undefined
      || item.client_identity_id !== successorClientIdentityId
    ) return;
    setPredecessorIds([...predecessorIds, item.id]);
  };
  return (
    <div className="space-y-4 rounded-xl border border-cyan-400/25 bg-cyan-400/5 p-4">
      <div><p className="font-semibold">{operationType === "REFINANCING" ? "Continuidade REFIN" : "Continuidade por RENEGOCIAÇÃO"}</p><p className="text-sm text-muted-foreground">O contrato atual {movement.contract_code ?? movement.id} será o único sucessor. Selecione um ou mais contratos anteriores do mesmo cliente canônico.</p></div>
      <FormField label="Buscar contratos anteriores" hint="Pesquise por contrato ou cliente; o nome é apenas informativo.">
        <div className="flex gap-2"><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Contrato ou cliente" /><Button type="button" variant="outline" disabled={searching || !query.trim()} onClick={search}>{searching ? "Buscando…" : "Buscar"}</Button></div>
      </FormField>
      <div className="space-y-2 rounded-lg border p-3">
        <p className="font-medium">Contratos anteriores selecionados: {selected.length}</p>
        {selected.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum contrato selecionado.</p> : selected.map((item) => (
          <div key={item.id} className="flex items-center justify-between gap-3 rounded-md bg-background/50 p-2 text-sm">
            <span><strong>{item.contract_code ?? item.id}</strong> · {item.client_name ?? "Cliente não informado"}</span>
            <Button type="button" size="sm" variant="ghost" onClick={() => toggle(item)}>Remover</Button>
          </div>
        ))}
      </div>
      {predecessors.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Resultados da busca</p>
          {predecessors.map((item) => {
            const selectedItem = predecessorIds.includes(item.id);
            const sameClient = successorClientIdentityId !== null
              && item.client_identity_id !== null
              && item.client_identity_id !== undefined
              && item.client_identity_id === successorClientIdentityId;
            return (
              <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                <span><strong>{item.contract_code ?? item.id}</strong> · {item.client_name ?? "Cliente não informado"}{!sameClient && <small className="ml-2 text-rose-400">Cliente canônico divergente ou indisponível</small>}</span>
                <Button type="button" size="sm" variant={selectedItem ? "secondary" : "outline"} disabled={!sameClient && !selectedItem} aria-pressed={selectedItem} onClick={() => toggle(item)}>{selectedItem ? "Desmarcar" : "Selecionar"}</Button>
              </div>
            );
          })}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Data efetiva"><Input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></FormField>
        <FormField label="Observação" hint={operationType === "RENEGOTIATION" ? "Obrigatória para auditoria." : "Opcional."}><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={255} /></FormField>
      </div>
    </div>
  );
}

function BankFields({ amountInput, setAmountInput, observedDate, setObservedDate, bankCode, setBankCode, justification, setJustification, difference }: {
  amountInput: string;
  setAmountInput: (value: string) => void;
  observedDate: string;
  setObservedDate: (value: string) => void;
  bankCode: TreasuryBankCode | "";
  setBankCode: (value: TreasuryBankCode | "") => void;
  justification: string;
  setJustification: (value: string) => void;
  difference: bigint | null;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Valor encontrado no banco"><Input inputMode="decimal" value={amountInput} onChange={(event) => setAmountInput(event.target.value)} placeholder="0,00" /></FormField>
      <FormField label="Data encontrada no banco"><Input type="date" value={observedDate} onChange={(event) => setObservedDate(event.target.value)} /></FormField>
      <FormField label="Banco / meio"><Select value={bankCode} onChange={(event) => setBankCode(event.target.value as TreasuryBankCode | "")}><option value="">Não informado</option>{Object.entries(bankLabels).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</Select></FormField>
      <div className="rounded-xl border p-3"><p className="text-xs uppercase tracking-wider text-muted-foreground">Diferença banco − sistema</p><p className={`mt-1 text-lg font-semibold ${difference === null || difference === 0n ? "" : "text-rose-400"}`}>{difference === null ? "Informe o valor" : formatCents(difference)}</p></div>
      <FormField label="Justificativa" hint={difference !== null && difference !== 0n ? "Obrigatória para divergência." : "Opcional quando os valores conferem."} className="sm:col-span-2"><Textarea value={justification} onChange={(event) => setJustification(event.target.value)} maxLength={4000} /></FormField>
    </div>
  );
}

function RenegotiationEconomics({ values, setters, valid }: {
  values: Record<keyof EconomicValues, string>;
  setters: {
    setOriginalPrincipal: (value: string) => void;
    setPrincipalPaid: (value: string) => void;
    setPrincipalRolled: (value: string) => void;
    setInterestPaid: (value: string) => void;
  };
  valid: boolean;
}) {
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div><p className="font-semibold">Valores econômicos comprovados</p><p className="text-sm text-muted-foreground">Informe os valores confirmados pela REMO. O sistema não reconstrói parcelas nem calcula o saldo por diferença entre contratos.</p></div>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Principal original"><Input inputMode="decimal" value={values.originalPrincipal} onChange={(event) => setters.setOriginalPrincipal(event.target.value)} /></FormField>
        <FormField label="Principal efetivamente pago"><Input inputMode="decimal" value={values.principalPaid} onChange={(event) => setters.setPrincipalPaid(event.target.value)} /></FormField>
        <FormField label="Principal rolado"><Input inputMode="decimal" value={values.principalRolled} onChange={(event) => setters.setPrincipalRolled(event.target.value)} /></FormField>
        <FormField label="Juros efetivamente pagos"><Input inputMode="decimal" value={values.interestPaid} onChange={(event) => setters.setInterestPaid(event.target.value)} /></FormField>
      </div>
      {!valid && <p className="text-sm text-amber-400">O principal original deve ser igual ao principal pago mais o principal rolado.</p>}
    </div>
  );
}

function ValidationHistory({ history, loading }: { history: TreasuryValidationHistory | null; loading: boolean }) {
  return (
    <div>
      <h3 className="font-semibold">Histórico de validações</h3>
      {loading ? <LoadingState label="Carregando histórico…" /> : history?.items.length ? (
        <div className="mt-3 space-y-3">{history.items.map((item) => <div key={item.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-3"><span>Versão {item.version}{item.is_current ? " · atual" : ""}</span><StatusBadge status={item.status} /></div><p className="mt-2">Sistema {formatMoney(item.system_amount_snapshot)} · Banco {formatMoney(item.observed_amount)} · Diferença {formatMoney(item.difference_amount)}</p><p className="text-xs text-muted-foreground">Banco em {formatDate(item.observed_date)} · validado em {formatDateTime(item.validated_at)}{item.bank_code ? ` · ${bankLabels[item.bank_code]}` : ""}</p>{item.justification && <p className="mt-1 text-xs">{item.justification}</p>}</div>)}</div>
      ) : <p className="mt-2 text-sm text-muted-foreground">Nenhuma validação anterior. O status atual é Pendente.</p>}
    </div>
  );
}

function parseEconomicValues(values: Record<keyof EconomicValues, string>): EconomicValues | null {
  if (Object.values(values).some((value) => !value.trim())) return null;
  const original = parseBrazilianMoneyToCents(values.originalPrincipal);
  const paid = parseBrazilianMoneyToCents(values.principalPaid);
  const rolled = parseBrazilianMoneyToCents(values.principalRolled);
  const interest = parseBrazilianMoneyToCents(values.interestPaid);
  if (original === null || paid === null || rolled === null || interest === null) return null;
  if ([original, paid, rolled, interest].some((value) => value < 0n)) return null;
  if (original !== paid + rolled) return null;
  return {
    originalPrincipal: centsToMoney(original),
    principalPaid: centsToMoney(paid),
    principalRolled: centsToMoney(rolled),
    interestPaid: centsToMoney(interest),
  };
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 font-medium">{value}</p></div>;
}
