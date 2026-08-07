import type {
  Cents, ContractFundingAllocation, FundingState, ReceiptComponentStatus,
  RevenueAllocationStatus, RevenueRecordView, RevenueStatus, TreasuryIncomingReceipt,
} from "@/types/funding";

function money(value: Cents): bigint {
  if (!/^-?\d+$/.test(value)) throw new Error("Valor monetário inválido na projeção de Receita.");
  return BigInt(value);
}

export function calculateApuratedAmount(receipt: TreasuryIncomingReceipt): Cents {
  return (
    money(receipt.principalAmount)
    + money(receipt.interestAmount)
    + money(receipt.iofAmount)
    + money(receipt.penaltyAmount)
    - money(receipt.discountAmount)
    - money(receipt.lossAmount)
  ).toString();
}

export function calculateComponentDifference(receipt: TreasuryIncomingReceipt): Cents {
  return (money(calculateApuratedAmount(receipt)) - money(receipt.paidAmountFromOperationalSource)).toString();
}

export function deriveComponentStatus(receipt: TreasuryIncomingReceipt): ReceiptComponentStatus {
  if (receipt.operationalStatus === "WAITING_WRITE_OFF" || !receipt.operationalWriteOffDate) return "COMPONENTS_INCOMPLETE";
  return money(calculateComponentDifference(receipt)) === 0n ? "COMPONENTS_MATCH" : "COMPONENTS_MISMATCH";
}

function allocationsAt(state: FundingState, contractId: string | undefined, date: string): ContractFundingAllocation[] {
  if (!contractId) return [];
  return state.contractFundingAllocations.filter((item) => item.fundingContractId === contractId
    && item.validFrom.slice(0, 10) <= date
    && (!item.validUntil || date < item.validUntil.slice(0, 10)));
}

export function deriveRevenueAllocationStatus(state: FundingState, receipt: TreasuryIncomingReceipt): RevenueAllocationStatus {
  if (receipt.status === "REVERSED") return "REVERSED";
  const shares = state.allocationReceiptShares.filter((item) => item.incomingReceiptId === receipt.id && item.status !== "REVERSED");
  if (shares.length === 0) {
    const referenceDate = receipt.operationalWriteOffDate ?? receipt.dueDate;
    return allocationsAt(state, receipt.fundingContractId, referenceDate).length === 0 ? "REVIEW_REQUIRED" : "NOT_CALCULATED";
  }
  if (state.revenueDivergences.some((item) => item.incomingReceiptId === receipt.id
    && ["FUNDING_COMPOSITION_NOT_FOUND", "ALLOCATION_TOTAL_MISMATCH"].includes(item.type)
    && ["OPEN", "IN_REVIEW"].includes(item.status))) return "DIVERGENT";
  return shares.every((item) => item.status === "CONFIRMED") ? "CONFIRMED" : "CALCULATED";
}

export function deriveRevenueStatus(state: FundingState, receipt: TreasuryIncomingReceipt): RevenueStatus {
  if (receipt.status === "CANCELLED") return "CANCELLED";
  if (receipt.status === "REVERSED") return "REVERSED";
  if (deriveComponentStatus(receipt) === "COMPONENTS_MISMATCH") return "COMPONENT_DIVERGENCE";
  if (["BANK_VALUE_MISMATCH", "BANK_MOVEMENT_NOT_FOUND"].includes(receipt.status)) return "BANK_DIVERGENCE";
  if (receipt.status === "PARTIALLY_VALIDATED") return "PARTIALLY_VALIDATED";
  if (receipt.operationalStatus !== "WRITTEN_OFF") return "PENDING_OPERATIONAL_DATA";
  if (receipt.bankValidationStatus !== "VALIDATED") return "PENDING_BANK_VALIDATION";
  const allocationStatus = deriveRevenueAllocationStatus(state, receipt);
  if (allocationStatus !== "CONFIRMED") return "PENDING_ALLOCATION";
  return "VALIDATED";
}

export function buildRevenueRecordView(state: FundingState, receipt: TreasuryIncomingReceipt): RevenueRecordView {
  const links = state.receiptBankReconciliations.filter((item) => item.incomingReceiptId === receipt.id && item.status === "ACTIVE");
  const movements = links.flatMap((link) => {
    const movement = state.bankMovements.find((item) => item.id === link.bankMovementId);
    return movement ? [movement] : [];
  });
  const referenceDate = receipt.operationalWriteOffDate ?? receipt.dueDate;
  const allocations = allocationsAt(state, receipt.fundingContractId, referenceDate).sort((left, right) => {
    const difference = money(right.amount) - money(left.amount);
    return difference > 0n ? 1 : difference < 0n ? -1 : left.id.localeCompare(right.id);
  });
  const main = allocations[0];
  const mainSource = state.fundingSources.find((item) => item.id === main?.fundingSourceId);
  const reconciledAmount = links.reduce((total, item) => total + money(item.amount), 0n);
  const bankAccounts = [...new Set(movements.map((item) => item.bankAccountId))];
  return {
    id: receipt.id,
    operationalReceiptId: receipt.id,
    treasuryIncomingReceiptId: receipt.id,
    contractCode: receipt.contractCode,
    maskedClientName: receipt.maskedClientName,
    installmentNumber: receipt.installmentNumber,
    totalInstallments: receipt.totalInstallments,
    dueDate: receipt.dueDate,
    operationalPaymentDate: receipt.operationalWriteOffDate,
    expectedInstallmentAmount: receipt.expectedAmount,
    paidAmount: receipt.paidAmountFromOperationalSource,
    operationalStatus: receipt.operationalStatus,
    observation: receipt.notes,
    financialOperator: receipt.responsibleUser,
    principalAmount: receipt.principalAmount,
    interestAmount: receipt.interestAmount,
    iofAmount: receipt.iofAmount,
    penaltyAmount: receipt.penaltyAmount,
    discountAmount: receipt.discountAmount,
    lossAmount: receipt.lossAmount,
    apuratedAmount: calculateApuratedAmount(receipt),
    componentDifference: calculateComponentDifference(receipt),
    componentStatus: deriveComponentStatus(receipt),
    paymentReference: {
      competence: (receipt.operationalWriteOffDate ?? receipt.dueDate).slice(0, 7),
      operationalReference: receipt.sourceReference,
      bankReferences: movements.map((item) => item.transactionReference),
      transactionDescriptions: movements.map((item) => item.payerDescription),
    },
    mainFundingSourceLabel: mainSource?.name ?? (main?.fundingSourceType === "REMO_OWN_CAPITAL" ? "Capital próprio REMO" : "Sem composição histórica"),
    fundingSourcesCount: allocations.length,
    bankAccountLabel: bankAccounts.join(", ") || "Não informada",
    bankDifference: (money(receipt.paidAmountFromOperationalSource) - reconciledAmount).toString(),
    bankValidationStatus: receipt.bankValidationStatus,
    reconciliationStatus: receipt.reconciliationStatus,
    allocationStatus: deriveRevenueAllocationStatus(state, receipt),
    revenueStatus: deriveRevenueStatus(state, receipt),
    createdAt: receipt.createdAt,
    updatedAt: receipt.updatedAt,
  };
}

export function buildRevenueRecords(state: FundingState): RevenueRecordView[] {
  return state.treasuryIncomingReceipts.map((receipt) => buildRevenueRecordView(state, receipt));
}
