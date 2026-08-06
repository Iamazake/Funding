export type Cents = string;
export type BasisPoints = number;
export type PersonType = "PF" | "PJ";

export type InvestorStatus = "PENDENTE" | "ATIVO" | "INATIVO" | "ENCERRADO";
export type RiskGrade = "BAIXO" | "MEDIO" | "ALTO";
export type ContributionStatus =
  | "PENDENTE" | "ATIVO" | "PARCIALMENTE_ALOCADO" | "TOTALMENTE_ALOCADO"
  | "EM_LIQUIDACAO" | "LIQUIDADO" | "LIQUIDADO_ANTECIPADAMENTE" | "CANCELADO";

export type CapitalRemunerationStatus =
  | "PREVISTA" | "A_VENCER" | "VENCE_HOJE" | "ATRASADA"
  | "PAGA" | "REINVESTIDA" | "QUITADA" | "CANCELADA";
export type RemunerationCalculationBase = "ORIGINAL_CONTRIBUTION_AMOUNT";
export type RemunerationSettlementMethod = "BANK_TRANSFER" | "REINVESTMENT" | "NOT_DEFINED";

export type FundingSourceType =
  | "INVESTOR_CONTRIBUTION" | "REMO_OWN_CAPITAL" | "OTHER_SOURCE" | "UNIDENTIFIED_SOURCE";
export type FundingSourceStatus = "ACTIVE" | "INACTIVE" | "PENDING_IDENTIFICATION";
export type FundingValidationStatus = "PENDING" | "VALID" | "DIVERGENT" | "CORRECTION_REQUIRED";
export type FundingContractStatus =
  | "DRAFT" | "PENDING_FUNDING" | "FUNDING_DIVERGENT" | "FUNDED" | "RELEASED" | "CANCELLED";

export type FundingDivergenceType =
  | "INSUFFICIENT_INVESTOR_BALANCE" | "FUNDING_TOTAL_MISMATCH" | "UNIDENTIFIED_FUNDING_SOURCE"
  | "DUPLICATED_CAPITAL_USAGE" | "MISSING_REMO_CAPITAL";
export type TreasuryDivergenceType = "BANK_AMOUNT_MISMATCH" | "BANK_MOVEMENT_NOT_FOUND";
export type DivergenceStatus = "OPEN" | "IN_REVIEW" | "RESOLVED" | "JUSTIFIED_EXCEPTION";
export type DivergenceResolutionType =
  | "REMO_OWN_CAPITAL" | "ADD_ANOTHER_INVESTOR" | "CORRECT_ALLOCATION"
  | "REGISTER_MISSING_CONTRIBUTION" | "CORRECT_BANK_MOVEMENT" | "JUSTIFIED_EXCEPTION";

export type IncomingReceiptStatus =
  | "WAITING_OPERATIONAL_WRITE_OFF" | "WAITING_BANK_VALIDATION" | "BANK_MOVEMENT_FOUND"
  | "BANK_VALUE_MISMATCH" | "BANK_MOVEMENT_NOT_FOUND" | "PARTIALLY_VALIDATED"
  | "VALIDATED" | "REVERSED" | "CANCELLED";
export type OperationalWriteOffStatus = "WAITING_WRITE_OFF" | "WRITTEN_OFF" | "REVERSED" | "CANCELLED";
export type IncomingBankValidationStatus = "PENDING" | "MOVEMENT_FOUND" | "VALUE_MISMATCH" | "MOVEMENT_NOT_FOUND" | "VALIDATED" | "REJECTED";
export type IncomingReconciliationStatus = "PENDING" | "PARTIAL" | "RECONCILED" | "DIVERGENT" | "REVERSED";
export type BankMovementStatus = "FOUND" | "NOT_FOUND" | "REVERSED";
export type ReceiptBankReconciliationStatus = "ACTIVE" | "REVERSED";

export type RevenueStatus =
  | "PENDING_OPERATIONAL_DATA" | "PENDING_BANK_VALIDATION" | "PENDING_ALLOCATION"
  | "PARTIALLY_VALIDATED" | "VALIDATED" | "COMPONENT_DIVERGENCE"
  | "BANK_DIVERGENCE" | "REVERSED" | "CANCELLED";
export type ReceiptComponentStatus = "COMPONENTS_MATCH" | "COMPONENTS_MISMATCH" | "COMPONENTS_INCOMPLETE";
export type RevenueAllocationStatus = "NOT_CALCULATED" | "CALCULATED" | "DIVERGENT" | "REVIEW_REQUIRED" | "CONFIRMED" | "REVERSED";
export type RevenueDivergenceType =
  | "RECEIPT_COMPONENT_MISMATCH" | "BANK_AMOUNT_MISMATCH" | "BANK_MOVEMENT_NOT_FOUND"
  | "FUNDING_COMPOSITION_NOT_FOUND" | "ALLOCATION_TOTAL_MISMATCH" | "PARTIAL_PAYMENT"
  | "DUPLICATED_RECEIPT" | "OPERATIONAL_STATUS_CONFLICT" | "REVERSED_AFTER_ALLOCATION";
export type RevenueDivergenceAction = "INVESTIGATE" | "ADD_NOTE" | "FIX_LINK" | "RECALCULATE" | "JUSTIFY" | "RESOLVE" | "REOPEN";
export type RevenueColumnDensity = "COMPACT" | "COMFORTABLE";
export type RevenueColumnKey =
  | "contract" | "installment" | "dueDate" | "paymentDate" | "expected" | "paid"
  | "status" | "operator" | "principal" | "interest" | "iof" | "loss" | "discount"
  | "apurated" | "componentDifference" | "paymentReference" | "funding" | "bankValidation" | "revenueStatus";

export type TreasuryEntryType =
  | "INVESTOR_CONTRIBUTION_RECEIVED" | "PMT_RECEIVED" | "PRINCIPAL_RECEIVED" | "INTEREST_RECEIVED"
  | "IOF_RECEIVED" | "PENALTY_RECEIVED" | "ADJUSTMENT_IN" | "REVERSAL_IN"
  | "LOAN_RELEASE" | "CAPITAL_REMUNERATION_PAID" | "CAPITAL_RETURNED" | "PJR_PAYMENT"
  | "OPERATING_EXPENSE" | "ADJUSTMENT_OUT" | "REVERSAL_OUT"
  | "CAPITAL_ALLOCATED" | "CAPITAL_DEALLOCATED" | "CAPITAL_REINVESTED" | "REMUNERATION_REINVESTED";
export type TreasuryDirection = "ENTRADA" | "SAIDA" | "TRANSFERENCIA_INTERNA";
export type TreasuryStatus = "PENDENTE" | "CONFIRMADO" | "CANCELADO" | "ESTORNADO";
export type ReconciliationStatus = "CONCILIADO" | "DIVERGENTE";

export interface InvestorContact { label: string; value: string; }
export interface DemoBankAccount { bank: string; branchMasked: string; accountMasked: string; pixMasked: string; }

export interface Investor {
  id: string; code: string; name: string; personType: PersonType; maskedDocument: string;
  riskGrade: RiskGrade; contractSigned: boolean; signedAt: string | null; paymentDay: number;
  status: InvestorStatus; contacts: InvestorContact[]; bankAccount: DemoBankAccount; notes: string;
  createdAt: string; updatedAt: string;
}

export interface Contribution {
  id: string; investorId: string; code: string; originalAmount: Cents; availableBalance: Cents;
  allocatedBalance: Cents; startDate: string; endDate: string; monthlyRateBps: BasisPoints;
  expectedMonthlyRemuneration: Cents; status: ContributionStatus; notes: string;
  createdAt: string; updatedAt: string;
}

export interface CapitalRemunerationHistory {
  id: string; action: string; description: string; date: string; responsibleUser: string;
}

export interface CapitalRemunerationEvent {
  id: string; investorId: string; contributionId: string; competence: string;
  originalContributionAmount: Cents; monthlyRateBps: BasisPoints;
  calculationBase: RemunerationCalculationBase; grossAmount: Cents; informedPjrAmount: Cents;
  netAmount: Cents; expectedDate: string; paymentDate?: string; status: CapitalRemunerationStatus;
  settlementMethod: RemunerationSettlementMethod; cashAccount?: string; notes: string;
  history: CapitalRemunerationHistory[];
}

export interface FundingSource {
  id: string; type: FundingSourceType; name: string; reference?: string;
  historicalAvailableAmount: Cents; status: FundingSourceStatus;
}

export type FundingLedgerEntryType = "ENTRY" | "RETURN" | "REINTEGRATION" | "REVERSAL";
export interface FundingLedgerEntry {
  id: string; fundingSourceId: string; contributionId?: string; type: FundingLedgerEntryType;
  amount: Cents; date: string; reference: string;
}

export interface FundingContract {
  id: string; contractCode: string; maskedClientName: string; operationDate: string; releaseDate: string;
  principalAmount: Cents; financedAmount: Cents; releasedAmount: Cents; installmentAmount: Cents;
  termMonths: number; interestRateBps: BasisPoints; status: FundingContractStatus;
  fundingValidationStatus: FundingValidationStatus; responsibleUser: string; notes: string;
  createdAt: string; updatedAt: string;
}

export interface ContractFundingAllocation {
  id: string; fundingContractId: string; fundingSourceType: FundingSourceType;
  contributionId?: string; investorId?: string; fundingSourceId?: string; amount: Cents;
  allocationDate: string; validFrom: string; validUntil?: string;
  historicalAvailableBalance: Cents; validationStatus: FundingValidationStatus;
  divergenceReason?: string; notes: string; supersededAt?: string; revisedFromId?: string;
}

export interface FundingDivergence {
  id: string; fundingContractId: string; type: FundingDivergenceType; expectedAmount: Cents;
  identifiedAmount: Cents; differenceAmount: Cents; description: string; status: DivergenceStatus;
  resolutionType?: DivergenceResolutionType; resolutionNotes?: string; resolvedAt?: string;
  resolvedBy?: string; createdAt: string;
}

export interface TreasuryIncomingReceipt {
  id: string; fundingContractId?: string; contractCode: string; maskedClientName: string;
  installmentNumber: number; totalInstallments: number; dueDate: string;
  operationalWriteOffDate?: string; expectedAmount: Cents; paidAmountFromOperationalSource: Cents;
  principalAmount: Cents; interestAmount: Cents; iofAmount: Cents; penaltyAmount: Cents;
  discountAmount: Cents; lossAmount: Cents; operationalStatus: OperationalWriteOffStatus;
  bankValidationStatus: IncomingBankValidationStatus; reconciliationStatus: IncomingReconciliationStatus;
  status: IncomingReceiptStatus; sourceReference: string; responsibleUser: string; notes: string;
  createdAt: string; updatedAt: string;
}

export interface BankMovement {
  id: string; bankAccountId: string; movementDate: string; amount: Cents;
  transactionReference: string; payerDescription: string; checkedBy: string; checkedAt: string;
  status: BankMovementStatus; notes: string;
}

export interface ReceiptBankReconciliation {
  id: string; incomingReceiptId: string; bankMovementId: string; amount: Cents;
  status: ReceiptBankReconciliationStatus; confirmedBy: string; confirmedAt: string; notes: string;
}

export interface TreasuryDivergence {
  id: string; incomingReceiptId: string; type: TreasuryDivergenceType; expectedAmount: Cents;
  reconciledAmount: Cents; differenceAmount: Cents; description: string; status: DivergenceStatus;
  resolutionNotes?: string; resolvedAt?: string; resolvedBy?: string; createdAt: string;
}

export interface RevenueDivergence {
  id: string; incomingReceiptId: string; type: RevenueDivergenceType;
  expectedAmount: Cents; actualAmount: Cents; differenceAmount: Cents;
  description: string; status: DivergenceStatus; sourceTreasuryDivergenceId?: string;
  resolutionNotes?: string; resolvedAt?: string; resolvedBy?: string; createdAt: string; updatedAt: string;
}

export interface RevenuePaymentReference {
  competence: string; operationalReference: string; bankReferences: string[];
  transactionDescriptions: string[];
}

export interface RevenueRecordView {
  id: string; operationalReceiptId: string; treasuryIncomingReceiptId?: string;
  contractCode: string; maskedClientName: string; installmentNumber: number;
  totalInstallments?: number; dueDate: string; operationalPaymentDate?: string;
  expectedInstallmentAmount: Cents; paidAmount: Cents; operationalStatus: OperationalWriteOffStatus;
  observation: string; financialOperator: string; principalAmount: Cents; interestAmount: Cents;
  iofAmount: Cents; penaltyAmount: Cents; discountAmount: Cents; lossAmount: Cents;
  apuratedAmount: Cents; componentDifference: Cents; componentStatus: ReceiptComponentStatus;
  paymentReference: RevenuePaymentReference; mainFundingSourceLabel: string; fundingSourcesCount: number;
  bankValidationStatus: IncomingBankValidationStatus; reconciliationStatus: IncomingReconciliationStatus;
  allocationStatus: RevenueAllocationStatus; revenueStatus: RevenueStatus; createdAt: string; updatedAt: string;
}

export interface RevenueColumnPreferences {
  visibleColumns: RevenueColumnKey[]; density: RevenueColumnDensity;
}

export interface AllocationReceiptShare {
  id: string; incomingReceiptId: string; contractFundingAllocationId: string;
  fundingSourceType: FundingSourceType; investorId?: string; contributionId?: string;
  allocationBps: BasisPoints; principalShare: Cents; interestShare: Cents; iofShare: Cents;
  penaltyShare: Cents; discountShare: Cents; lossShare: Cents;
  iofDestinationStatus: "RULE_TO_CONFIRM"; status: RevenueAllocationStatus; calculatedAt: string;
}

export interface TreasuryEntry {
  id: string; investorId?: string; contributionId?: string; capitalRemunerationEventId?: string;
  fundingContractId?: string; incomingReceiptId?: string; bankMovementId?: string;
  type: TreasuryEntryType; direction: TreasuryDirection; amount: Cents; date: string;
  competence: string; cashAccount: string; status: TreasuryStatus; owner: string;
  reference: string; notes: string; createdAt: string;
}

export type AuditEntity = "INVESTOR" | "CONTRIBUTION" | "CAPITAL_REMUNERATION" | "CONTRACT" | "FUNDING_ALLOCATION" | "BANK_MOVEMENT" | "DIVERGENCE" | "INCOMING_RECEIPT" | "REVENUE" | "TREASURY" | "RECONCILIATION" | "SYSTEM";
export interface AuditEvent {
  id: string; entity: AuditEntity; entityId: string; action: string; description: string;
  date: string; demoUser: string;
}

export interface Reconciliation {
  id: string; cashAccount: string; calculatedBalance: Cents; informedBalance: Cents;
  difference: Cents; status: ReconciliationStatus; date: string; owner: string; notes: string;
}

export interface FundingState {
  version: 4; investors: Investor[]; contributions: Contribution[];
  capitalRemunerationEvents: CapitalRemunerationEvent[]; fundingSources: FundingSource[];
  fundingLedgerEntries: FundingLedgerEntry[]; fundingContracts: FundingContract[];
  contractFundingAllocations: ContractFundingAllocation[]; fundingDivergences: FundingDivergence[];
  treasuryIncomingReceipts: TreasuryIncomingReceipt[]; bankMovements: BankMovement[];
  receiptBankReconciliations: ReceiptBankReconciliation[]; treasuryDivergences: TreasuryDivergence[];
  revenueDivergences: RevenueDivergence[]; revenueColumnPreferences: RevenueColumnPreferences;
  allocationReceiptShares: AllocationReceiptShare[]; treasuryEntries: TreasuryEntry[];
  auditEvents: AuditEvent[]; reconciliations: Reconciliation[];
}

export interface TreasurySummary {
  principalManaged: Cents; availableBalance: Cents; allocatedCapital: Cents;
  accumulatedCapital: Cents; accumulatedInterest: Cents; returnedCapital: Cents;
  pjr: Cents; reinvestedCapital: Cents; reinvestedInterest: Cents;
  pendingPayments: Cents; overduePayments: Cents; projectedThirtyDays: Cents; cashBalance: Cents;
}

export type InvestorInput = Omit<Investor, "id" | "code" | "createdAt" | "updatedAt">;
export type ContributionInput = Omit<Contribution, "id" | "code" | "createdAt" | "updatedAt" | "expectedMonthlyRemuneration">;
export type CapitalRemunerationInput = Omit<CapitalRemunerationEvent, "id" | "history" | "originalContributionAmount" | "monthlyRateBps" | "grossAmount" | "netAmount">;
export type TreasuryEntryInput = Omit<TreasuryEntry, "id" | "createdAt">;
export type FundingContractInput = Omit<FundingContract, "id" | "createdAt" | "updatedAt" | "status" | "fundingValidationStatus">;
export type ContractFundingAllocationInput = Omit<ContractFundingAllocation, "id" | "fundingContractId" | "validFrom" | "historicalAvailableBalance" | "validationStatus" | "divergenceReason">;
export type TreasuryIncomingReceiptInput = Omit<TreasuryIncomingReceipt, "id" | "bankValidationStatus" | "reconciliationStatus" | "status" | "createdAt" | "updatedAt">;
export type BankMovementInput = Omit<BankMovement, "id">;
export type ReceiptBankReconciliationInput = Pick<ReceiptBankReconciliation, "incomingReceiptId" | "amount" | "notes">;

export interface PaymentBatchInput { remunerationIds: string[]; date: string; cashAccount: string; owner: string; notes: string; }
export interface ContractReleaseInput { date: string; cashAccount: string; owner: string; transactionReference: string; notes: string; }
export interface ReconciliationInput { cashAccount: string; informedBalance: Cents; date: string; owner: string; notes: string; }
export interface ChartPoint { label: string; value: number; secondaryValue?: number; }
