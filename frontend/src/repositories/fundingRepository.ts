import { cloneDemoState } from "@/data/demoFundingState";
import { buildRevenueRecords, calculateApuratedAmount, calculateComponentDifference, deriveComponentStatus } from "@/lib/revenue";
import type {
  AllocationReceiptShare, AuditEntity, BankMovement, BankMovementInput,
  CapitalRemunerationEvent, CapitalRemunerationInput, Cents, ContractFundingAllocation,
  ContractFundingAllocationInput, ContractReleaseInput, Contribution, ContributionInput,
  DivergenceResolutionType, FundingContract, FundingContractInput, FundingDivergence,
  FundingDivergenceType, FundingState, Investor, InvestorInput, PaymentBatchInput,
  ReceiptBankReconciliation, ReceiptBankReconciliationInput, Reconciliation,
  ReconciliationInput, RevenueColumnPreferences, RevenueDivergence, RevenueDivergenceAction,
  RevenueDivergenceType, RevenueRecordView, TreasuryDivergence, TreasuryDivergenceType, TreasuryEntry,
  TreasuryEntryInput, TreasuryIncomingReceipt, TreasuryIncomingReceiptInput, TreasurySummary,
} from "@/types/funding";

export const FUNDING_STORAGE_KEY = "remo-funding-demo-v4";
export const LEGACY_V3_STORAGE_KEY = "remo-funding-demo-v3";
export const LEGACY_V2_STORAGE_KEY = "remo-funding-demo-v2";
export const LEGACY_FUNDING_STORAGE_KEY = "remo-funding-demo-v1";
const DEMO_USER = "Usuário Demonstrativo";

export interface StorageAdapter {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export class RepositoryValidationError extends Error {
  constructor(message: string) { super(message); this.name = "RepositoryValidationError"; }
}

export interface RepositoryOptions { now?: () => Date; idFactory?: () => string; }

function defaultIdFactory(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isFundingState(value: unknown): value is FundingState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Record<keyof FundingState, unknown>>;
  return candidate.version === 4
    && ["investors", "contributions", "capitalRemunerationEvents", "fundingSources", "fundingLedgerEntries",
      "fundingContracts", "contractFundingAllocations", "fundingDivergences", "treasuryIncomingReceipts",
      "bankMovements", "receiptBankReconciliations", "treasuryDivergences", "revenueDivergences", "allocationReceiptShares",
      "treasuryEntries", "auditEvents", "reconciliations"]
      .every((key) => Array.isArray(candidate[key as keyof FundingState]))
    && Boolean(candidate.revenueColumnPreferences && typeof candidate.revenueColumnPreferences === "object");
}

export function cents(value: Cents): bigint {
  if (!/^-?\d+$/.test(value)) throw new RepositoryValidationError("Valor monetário deve ser uma string inteira de centavos.");
  return BigInt(value);
}

export function centsString(value: bigint): Cents { return value.toString(); }
export function sumCents(values: Cents[]): Cents { return centsString(values.reduce((total, value) => total + cents(value), 0n)); }
function absolute(value: bigint): bigint { return value < 0n ? -value : value; }
function dateOnly(date: Date): string { return date.toISOString().slice(0, 10); }
function monthOf(date: string): string { return date.slice(0, 7); }
function addDays(date: Date, days: number): Date { const result = new Date(date); result.setUTCDate(result.getUTCDate() + days); return result; }

/** Half-up rounding, entirely in integer cents. */
export function calculateCapitalRemuneration(originalAmount: Cents, monthlyRateBps: number): Cents {
  if (!Number.isInteger(monthlyRateBps) || monthlyRateBps < 0) throw new RepositoryValidationError("A taxa deve ser informada em basis points inteiros.");
  const numerator = cents(originalAmount) * BigInt(monthlyRateBps);
  return centsString((numerator + 5_000n) / 10_000n);
}

/** Deterministic largest-remainder split; returned parts always sum exactly to total. */
export function proportionalSplit(total: Cents, weights: Cents[]): Cents[] {
  const amount = cents(total); const parsed = weights.map(cents);
  const weightTotal = parsed.reduce((sum, value) => sum + value, 0n);
  if (amount < 0n || parsed.some((value) => value < 0n) || weightTotal <= 0n) throw new RepositoryValidationError("Total e pesos do rateio devem ser não negativos, com peso total positivo.");
  const parts = parsed.map((weight) => amount * weight / weightTotal);
  const remainders = parsed.map((weight, index) => ({ index, remainder: amount * weight % weightTotal }));
  let missing = amount - parts.reduce((sum, value) => sum + value, 0n);
  remainders.sort((left, right) => left.remainder === right.remainder ? left.index - right.index : left.remainder > right.remainder ? -1 : 1);
  for (let index = 0; missing > 0n; index += 1, missing -= 1n) parts[remainders[index % remainders.length].index] += 1n;
  return parts.map(centsString);
}

function allocationValidAt(item: ContractFundingAllocation, date: string): boolean {
  return item.validFrom.slice(0, 10) <= date && (!item.validUntil || date < item.validUntil.slice(0, 10));
}

function currentAllocations(state: FundingState, fundingContractId?: string): ContractFundingAllocation[] {
  return state.contractFundingAllocations.filter((item) => !item.supersededAt && (!fundingContractId || item.fundingContractId === fundingContractId));
}

export function getContractAllocationsAt(state: FundingState, fundingContractId: string, date: string): ContractFundingAllocation[] {
  return state.contractFundingAllocations.filter((item) => item.fundingContractId === fundingContractId && allocationValidAt(item, date));
}

export function calculateHistoricalAvailableBalance(state: FundingState, fundingSourceId: string, operationDate: string): Cents {
  const ledgerBalance = state.fundingLedgerEntries
    .filter((entry) => entry.fundingSourceId === fundingSourceId && entry.date <= operationDate)
    .reduce((balance, entry) => balance + (["ENTRY", "REINTEGRATION", "REVERSAL"].includes(entry.type) ? cents(entry.amount) : -cents(entry.amount)), 0n);
  const allocated = state.contractFundingAllocations
    .filter((entry) => entry.fundingSourceId === fundingSourceId && entry.allocationDate <= operationDate && allocationValidAt(entry, operationDate))
    .reduce((total, entry) => total + cents(entry.amount), 0n);
  return centsString(ledgerBalance - allocated);
}

export function computeCashBalance(entries: TreasuryEntry[], cashAccount?: string): Cents {
  const balance = entries.filter((entry) => entry.status === "CONFIRMADO" && entry.direction !== "TRANSFERENCIA_INTERNA")
    .filter((entry) => !cashAccount || entry.cashAccount === cashAccount)
    .reduce((total, entry) => total + (entry.direction === "ENTRADA" ? cents(entry.amount) : -cents(entry.amount)), 0n);
  return centsString(balance);
}

export function computeTreasurySummary(state: FundingState, today = new Date()): TreasurySummary {
  const confirmed = state.treasuryEntries.filter((entry) => entry.status === "CONFIRMADO");
  const byType = (...types: TreasuryEntry["type"][]): bigint => confirmed.filter((entry) => types.includes(entry.type)).reduce((sum, entry) => sum + cents(entry.amount), 0n);
  const open = state.capitalRemunerationEvents.filter((item) => !["PAGA", "REINVESTIDA", "QUITADA", "CANCELADA"].includes(item.status));
  const todayText = dateOnly(today); const endText = dateOnly(addDays(today, 30));
  const validatedReceipts = state.treasuryIncomingReceipts.filter((item) => item.status === "VALIDATED");
  return {
    principalManaged: centsString(byType("INVESTOR_CONTRIBUTION_RECEIVED")),
    availableBalance: sumCents(state.contributions.filter((item) => item.status !== "CANCELADO").map((item) => item.availableBalance)),
    allocatedCapital: centsString(byType("CAPITAL_ALLOCATED") - byType("CAPITAL_DEALLOCATED")),
    accumulatedCapital: sumCents(validatedReceipts.map((item) => item.principalAmount)),
    accumulatedInterest: sumCents(validatedReceipts.map((item) => item.interestAmount)),
    returnedCapital: centsString(byType("CAPITAL_RETURNED")), pjr: centsString(byType("PJR_PAYMENT")),
    reinvestedCapital: centsString(byType("CAPITAL_REINVESTED")), reinvestedInterest: centsString(byType("REMUNERATION_REINVESTED")),
    pendingPayments: sumCents(open.map((item) => item.netAmount)), overduePayments: sumCents(open.filter((item) => item.status === "ATRASADA" || item.expectedDate < todayText).map((item) => item.netAmount)),
    projectedThirtyDays: sumCents(open.filter((item) => item.expectedDate >= todayText && item.expectedDate <= endText).map((item) => item.netAmount)),
    cashBalance: computeCashBalance(state.treasuryEntries),
  };
}

type LegacyRecord = Record<string, unknown>;
function records(value: unknown): LegacyRecord[] { return Array.isArray(value) ? value.filter((item): item is LegacyRecord => Boolean(item) && typeof item === "object") : []; }
function stringValue(record: LegacyRecord, key: string, fallback = ""): string { return typeof record[key] === "string" ? record[key] as string : fallback; }
function legacyRateToBps(value: unknown): number { const text = typeof value === "string" ? value.replace(",", ".") : "0"; const match = text.match(/^(\d+)(?:\.(\d{1,2}))?$/); return match ? Number.parseInt(match[1], 10) * 100 + Number.parseInt((match[2] ?? "").padEnd(2, "0"), 10) : 0; }

function migrateVersionOne(value: LegacyRecord): FundingState {
  const base = cloneDemoState(); const investors = records(value.investors); const contributions = records(value.contributions); const retiredEvents = records(value.dividendEvents);
  const validInvestors: Investor[] = investors.filter((item) => typeof item.id === "string" && typeof item.name === "string").map((item) => ({
    id: stringValue(item, "id"), code: stringValue(item, "code", "INV-MIGRADO"), name: stringValue(item, "name", "Investidor migrado"), personType: item.personType === "PJ" ? "PJ" : "PF", maskedDocument: stringValue(item, "maskedDocument", "***"), riskGrade: item.riskGrade === "BAIXO" || item.riskGrade === "ALTO" ? item.riskGrade : "MEDIO", contractSigned: item.contractSigned === true, signedAt: typeof item.signedAt === "string" ? item.signedAt : null, paymentDay: typeof item.paymentDay === "number" ? Math.trunc(item.paymentDay) : 10, status: ["PENDENTE", "ATIVO", "INATIVO", "ENCERRADO"].includes(String(item.status)) ? item.status as Investor["status"] : "PENDENTE", contacts: Array.isArray(item.contacts) ? item.contacts as Investor["contacts"] : [], bankAccount: item.bankAccount && typeof item.bankAccount === "object" ? item.bankAccount as Investor["bankAccount"] : { bank: "Não informado", branchMasked: "****", accountMasked: "*****-**", pixMasked: "***" }, notes: stringValue(item, "notes"), createdAt: stringValue(item, "createdAt", new Date(0).toISOString()), updatedAt: stringValue(item, "updatedAt", new Date(0).toISOString()),
  }));
  const investorIds = new Set(validInvestors.map((item) => item.id));
  const validContributions: Contribution[] = contributions.filter((item) => typeof item.id === "string" && investorIds.has(stringValue(item, "investorId"))).map((item) => { const rate = legacyRateToBps(item.monthlyRate); const originalAmount = /^\d+$/.test(stringValue(item, "originalAmount")) ? stringValue(item, "originalAmount") : "0"; return { id: stringValue(item, "id"), investorId: stringValue(item, "investorId"), code: stringValue(item, "code", "APT-MIGRADO"), originalAmount, availableBalance: /^\d+$/.test(stringValue(item, "availableBalance")) ? stringValue(item, "availableBalance") : originalAmount, allocatedBalance: /^\d+$/.test(stringValue(item, "allocatedBalance")) ? stringValue(item, "allocatedBalance") : "0", startDate: stringValue(item, "startDate", "2026-01-01"), endDate: stringValue(item, "endDate", "2027-01-01"), monthlyRateBps: rate, expectedMonthlyRemuneration: calculateCapitalRemuneration(originalAmount, rate), status: ["PENDENTE", "ATIVO", "PARCIALMENTE_ALOCADO", "TOTALMENTE_ALOCADO", "EM_LIQUIDACAO", "LIQUIDADO", "LIQUIDADO_ANTECIPADAMENTE", "CANCELADO"].includes(String(item.status)) ? item.status as Contribution["status"] : "PENDENTE", notes: stringValue(item, "notes"), createdAt: stringValue(item, "createdAt", new Date(0).toISOString()), updatedAt: stringValue(item, "updatedAt", new Date(0).toISOString()) }; });
  const byContribution = new Map(validContributions.map((item) => [item.id, item]));
  const statusMap: Record<string, CapitalRemunerationEvent["status"]> = { PREVISTO: "PREVISTA", A_VENCER: "A_VENCER", VENCE_HOJE: "VENCE_HOJE", ATRASADO: "ATRASADA", PAGO: "PAGA", REINVESTIDO: "REINVESTIDA", QUITADO: "QUITADA", CANCELADO: "CANCELADA" };
  const migratedEvents = retiredEvents.flatMap((item) => { const contribution = byContribution.get(stringValue(item, "contributionId")); if (!contribution) return []; const gross = calculateCapitalRemuneration(contribution.originalAmount, contribution.monthlyRateBps); const pjr = /^\d+$/.test(stringValue(item, "pjrAmount")) ? stringValue(item, "pjrAmount") : "0"; return [{ id: stringValue(item, "id").replace(/^div-/, "rem-"), investorId: contribution.investorId, contributionId: contribution.id, competence: stringValue(item, "competence"), originalContributionAmount: contribution.originalAmount, monthlyRateBps: contribution.monthlyRateBps, calculationBase: "ORIGINAL_CONTRIBUTION_AMOUNT" as const, grossAmount: gross, informedPjrAmount: pjr, netAmount: centsString(cents(gross) - cents(pjr)), expectedDate: stringValue(item, "dueDate"), paymentDate: typeof item.paidAt === "string" ? item.paidAt : undefined, status: statusMap[stringValue(item, "status")] ?? "PREVISTA", settlementMethod: item.status === "REINVESTIDO" ? "REINVESTMENT" as const : item.status === "PAGO" ? "BANK_TRANSFER" as const : "NOT_DEFINED" as const, notes: stringValue(item, "notes"), history: [{ id: `remh-${stringValue(item, "id")}`, action: "MIGRACAO", description: "Evento migrado do armazenamento demonstrativo v1.", date: new Date(0).toISOString(), responsibleUser: DEMO_USER }] }]; });
  return { ...base, investors: validInvestors.length ? validInvestors : base.investors, contributions: validContributions.length ? validContributions : base.contributions, capitalRemunerationEvents: migratedEvents.length ? migratedEvents : base.capitalRemunerationEvents, auditEvents: [...base.auditEvents, { id: "aud-migration-v1-v4", entity: "SYSTEM", entityId: "demo", action: "MIGRACAO_V4", description: "Estado v1 migrado; cadastros comerciais retirados, remunerações preservadas e Receita vinculada às entradas.", date: new Date(0).toISOString(), demoUser: DEMO_USER }] };
}

function migrateVersionThree(legacy: LegacyRecord): FundingState {
  const base = cloneDemoState();
  const arrayKeys = [
    "investors", "contributions", "capitalRemunerationEvents", "fundingSources", "fundingLedgerEntries",
    "fundingContracts", "contractFundingAllocations", "fundingDivergences", "treasuryIncomingReceipts",
    "bankMovements", "receiptBankReconciliations", "treasuryDivergences", "treasuryEntries", "auditEvents", "reconciliations",
  ] as const;
  const preserved = Object.fromEntries(arrayKeys.flatMap((key) => Array.isArray(legacy[key]) ? [[key, legacy[key]]] : []));
  const previouslyValidated = new Set(records(legacy.treasuryIncomingReceipts).filter((item) => item.status === "VALIDATED").map((item) => stringValue(item, "id")));
  const shares: AllocationReceiptShare[] = records(legacy.allocationReceiptShares).map((item) => ({
    id: stringValue(item, "id"), incomingReceiptId: stringValue(item, "incomingReceiptId"),
    contractFundingAllocationId: stringValue(item, "contractFundingAllocationId"),
    fundingSourceType: item.fundingSourceType as AllocationReceiptShare["fundingSourceType"],
    investorId: typeof item.investorId === "string" ? item.investorId : undefined,
    contributionId: typeof item.contributionId === "string" ? item.contributionId : undefined,
    allocationBps: typeof item.allocationBps === "number" ? item.allocationBps : 0,
    principalShare: stringValue(item, "principalShare", "0"), interestShare: stringValue(item, "interestShare", "0"),
    iofShare: "0", penaltyShare: stringValue(item, "penaltyShare", "0"), discountShare: stringValue(item, "discountShare", "0"),
    lossShare: stringValue(item, "lossShare", "0"), iofDestinationStatus: "RULE_TO_CONFIRM",
    status: item.status === "CONFIRMED" || previouslyValidated.has(stringValue(item, "incomingReceiptId")) ? "CONFIRMED" : "CALCULATED",
    calculatedAt: stringValue(item, "calculatedAt", new Date(0).toISOString()),
  }));
  const migrated = { ...base, ...preserved, version: 4, allocationReceiptShares: shares } as FundingState;
  migrated.revenueDivergences = [];
  migrated.revenueColumnPreferences = base.revenueColumnPreferences;
  migrated.treasuryIncomingReceipts.forEach((receipt) => {
    if (deriveComponentStatus(receipt) !== "COMPONENTS_MISMATCH") return;
    migrated.revenueDivergences.push({
      id: `revdiv-migrated-${receipt.id}`, incomingReceiptId: receipt.id, type: "RECEIPT_COMPONENT_MISMATCH",
      expectedAmount: receipt.paidAmountFromOperationalSource, actualAmount: calculateApuratedAmount(receipt),
      differenceAmount: absolute(cents(calculateComponentDifference(receipt))).toString(),
      description: "Diferença entre os componentes operacionais e o valor pago, identificada na migração v4.",
      status: "OPEN", createdAt: receipt.updatedAt, updatedAt: receipt.updatedAt,
    });
  });
  migrated.auditEvents.push({
    id: "aud-migration-v4", entity: "SYSTEM", entityId: "demo", action: "MODULO_RECEITA_V4",
    description: "Estado v3 migrado sem duplicar recebimentos; Receita passou a ser uma projeção do mesmo identificador.",
    date: new Date(0).toISOString(), demoUser: DEMO_USER,
  });
  return migrated;
}

/** Migrates the retired v2 origination model into contracts and incoming receipts. */
export function migrateFundingState(value: unknown): FundingState {
  const base = cloneDemoState(); if (!value || typeof value !== "object") return base;
  const legacy = value as LegacyRecord; if (legacy.version === 3) return migrateVersionThree(legacy); if (legacy.version === 1) return migrateVersionOne(legacy); if (legacy.version !== 2) return base;
  const legacyContracts = records(legacy.saleOperations); const legacyAllocations = records(legacy.saleFundingAllocations); const legacyDivergences = records(legacy.fundingDivergences); const legacyReceipts = records(legacy.operationalReceipts); const legacyEntries = records(legacy.treasuryEntries); const legacyShares = records(legacy.allocationReceiptShares);
  const fundingContracts: FundingContract[] = legacyContracts.map((item) => ({ id: stringValue(item, "id"), contractCode: stringValue(item, "contractCode"), maskedClientName: stringValue(item, "maskedClientName", "Cliente ***"), operationDate: stringValue(item, "operationDate"), releaseDate: stringValue(item, "releaseDate"), principalAmount: stringValue(item, "principalAmount", "0"), financedAmount: stringValue(item, "financedAmount", "0"), releasedAmount: stringValue(item, "releasedAmount", "0"), installmentAmount: stringValue(item, "installmentAmount", "0"), termMonths: typeof item.termMonths === "number" ? item.termMonths : 0, interestRateBps: typeof item.interestRateBps === "number" ? item.interestRateBps : 0, status: item.status === "DIVERGENT" || item.status === "CORRECTION_REQUIRED" ? "FUNDING_DIVERGENT" : item.status === "DRAFT" ? "DRAFT" : item.status === "CANCELLED" ? "CANCELLED" : "RELEASED", fundingValidationStatus: ["PENDING", "VALID", "DIVERGENT", "CORRECTION_REQUIRED"].includes(String(item.fundingValidationStatus)) ? item.fundingValidationStatus as FundingContract["fundingValidationStatus"] : "PENDING", responsibleUser: stringValue(item, "responsibleUser", DEMO_USER), notes: stringValue(item, "notes"), createdAt: stringValue(item, "createdAt", new Date(0).toISOString()), updatedAt: stringValue(item, "updatedAt", new Date(0).toISOString()) }));
  const contractFundingAllocations: ContractFundingAllocation[] = legacyAllocations.map((item) => ({ id: stringValue(item, "id"), fundingContractId: stringValue(item, "saleOperationId"), fundingSourceType: item.fundingSourceType as ContractFundingAllocation["fundingSourceType"], contributionId: typeof item.contributionId === "string" ? item.contributionId : undefined, investorId: typeof item.investorId === "string" ? item.investorId : undefined, fundingSourceId: typeof item.fundingSourceId === "string" ? item.fundingSourceId : undefined, amount: stringValue(item, "amount", "0"), allocationDate: stringValue(item, "allocationDate"), validFrom: stringValue(item, "allocationDate"), historicalAvailableBalance: stringValue(item, "historicalAvailableBalance", "0"), validationStatus: item.validationStatus as ContractFundingAllocation["validationStatus"], divergenceReason: typeof item.divergenceReason === "string" ? item.divergenceReason : undefined, notes: stringValue(item, "notes"), supersededAt: typeof item.supersededAt === "string" ? item.supersededAt : undefined, revisedFromId: typeof item.revisedFromId === "string" ? item.revisedFromId : undefined }));
  contractFundingAllocations.forEach((item) => { if (item.supersededAt) item.validUntil = item.supersededAt; });
  const fundingTypes: FundingDivergenceType[] = ["INSUFFICIENT_INVESTOR_BALANCE", "FUNDING_TOTAL_MISMATCH", "UNIDENTIFIED_FUNDING_SOURCE", "DUPLICATED_CAPITAL_USAGE", "MISSING_REMO_CAPITAL"];
  const fundingDivergences: FundingDivergence[] = legacyDivergences.filter((item) => fundingTypes.includes(item.type as FundingDivergenceType)).map((item) => ({ id: stringValue(item, "id"), fundingContractId: stringValue(item, "saleOperationId"), type: item.type as FundingDivergenceType, expectedAmount: stringValue(item, "expectedAmount", "0"), identifiedAmount: stringValue(item, "identifiedAmount", "0"), differenceAmount: stringValue(item, "differenceAmount", "0"), description: stringValue(item, "description"), status: item.status as FundingDivergence["status"], resolutionType: item.resolutionType as FundingDivergence["resolutionType"], resolutionNotes: typeof item.resolutionNotes === "string" ? item.resolutionNotes : undefined, resolvedAt: typeof item.resolvedAt === "string" ? item.resolvedAt : undefined, resolvedBy: typeof item.resolvedBy === "string" ? item.resolvedBy : undefined, createdAt: stringValue(item, "createdAt", new Date(0).toISOString()) }));
  const mappedEntries: TreasuryEntry[] = legacyEntries.map((item) => ({ id: stringValue(item, "id"), investorId: typeof item.investorId === "string" ? item.investorId : undefined, contributionId: typeof item.contributionId === "string" ? item.contributionId : undefined, capitalRemunerationEventId: typeof item.capitalRemunerationEventId === "string" ? item.capitalRemunerationEventId : undefined, fundingContractId: typeof item.saleOperationId === "string" ? item.saleOperationId : undefined, incomingReceiptId: typeof item.operationalReceiptId === "string" ? item.operationalReceiptId : undefined, type: item.type as TreasuryEntry["type"], direction: item.direction as TreasuryEntry["direction"], amount: stringValue(item, "amount", "0"), date: stringValue(item, "date"), competence: stringValue(item, "competence"), cashAccount: stringValue(item, "cashAccount"), status: item.status as TreasuryEntry["status"], owner: stringValue(item, "owner", DEMO_USER), reference: stringValue(item, "reference"), notes: stringValue(item, "notes"), createdAt: stringValue(item, "createdAt", new Date(0).toISOString()) }));
  mappedEntries.forEach((item) => {
    if (item.type === "LOAN_RELEASE") item.direction = "SAIDA";
  });
  const bankMovements: BankMovement[] = []; const links: ReceiptBankReconciliation[] = [];
  const incoming: TreasuryIncomingReceipt[] = legacyReceipts.map((item, index) => { const receiptId = stringValue(item, "id"); const contract = fundingContracts.find((value) => value.contractCode === stringValue(item, "contractCode")); const cashEntry = mappedEntries.find((entry) => entry.incomingReceiptId === receiptId && entry.type === "PMT_RECEIVED" && entry.status === "CONFIRMADO"); if (cashEntry) { const bankId = `bank-migrated-${index + 1}`; cashEntry.bankMovementId = bankId; bankMovements.push({ id: bankId, bankAccountId: cashEntry.cashAccount, movementDate: cashEntry.date, amount: cashEntry.amount, transactionReference: cashEntry.reference, payerDescription: "Pagador migrado ***", checkedBy: cashEntry.owner, checkedAt: cashEntry.createdAt, status: "FOUND", notes: "Movimento reconstruído do caixa demonstrativo v2." }); links.push({ id: `link-migrated-${index + 1}`, incomingReceiptId: receiptId, bankMovementId: bankId, amount: cashEntry.amount, status: "ACTIVE", confirmedBy: cashEntry.owner, confirmedAt: cashEntry.createdAt, notes: "Associação reconstruída na migração v3." }); } const validated = Boolean(cashEntry); const totalPaid = stringValue(item, "totalPaid", "0"); return { id: receiptId, fundingContractId: contract?.id, contractCode: stringValue(item, "contractCode"), maskedClientName: contract?.maskedClientName ?? "Cliente ***", installmentNumber: typeof item.installmentNumber === "number" ? item.installmentNumber : 0, totalInstallments: contract?.termMonths ?? 0, dueDate: stringValue(item, "receiptDate"), operationalWriteOffDate: stringValue(item, "receiptDate"), expectedAmount: totalPaid, paidAmountFromOperationalSource: totalPaid, principalAmount: stringValue(item, "principalAmount", "0"), interestAmount: stringValue(item, "interestAmount", "0"), iofAmount: stringValue(item, "iofAmount", "0"), penaltyAmount: stringValue(item, "penaltyAmount", "0"), discountAmount: stringValue(item, "discountAmount", "0"), lossAmount: stringValue(item, "lossAmount", "0"), operationalStatus: item.status === "REVERSED" ? "REVERSED" : "WRITTEN_OFF", bankValidationStatus: validated ? "VALIDATED" : "PENDING", reconciliationStatus: validated ? "RECONCILED" : "PENDING", status: item.status === "REVERSED" ? "REVERSED" : validated ? "VALIDATED" : "WAITING_BANK_VALIDATION", sourceReference: `MIGRADO-V2:${receiptId}`, responsibleUser: cashEntry?.owner ?? DEMO_USER, notes: "Recebimento operacional migrado do armazenamento v2.", createdAt: cashEntry?.createdAt ?? new Date(0).toISOString(), updatedAt: cashEntry?.createdAt ?? new Date(0).toISOString() }; });
  const allocationReceiptShares: AllocationReceiptShare[] = legacyShares.map((item) => ({ id: stringValue(item, "id"), incomingReceiptId: stringValue(item, "operationalReceiptId"), contractFundingAllocationId: stringValue(item, "saleFundingAllocationId"), fundingSourceType: item.fundingSourceType as AllocationReceiptShare["fundingSourceType"], investorId: typeof item.investorId === "string" ? item.investorId : undefined, contributionId: typeof item.contributionId === "string" ? item.contributionId : undefined, allocationBps: typeof item.allocationBps === "number" ? item.allocationBps : 0, principalShare: stringValue(item, "principalShare", "0"), interestShare: stringValue(item, "interestShare", "0"), iofShare: "0", penaltyShare: "0", discountShare: stringValue(item, "discountShare", "0"), lossShare: stringValue(item, "lossShare", "0"), iofDestinationStatus: "RULE_TO_CONFIRM", status: "CALCULATED", calculatedAt: stringValue(item, "calculatedAt", new Date(0).toISOString()) }));
  return { ...base, investors: Array.isArray(legacy.investors) ? legacy.investors as FundingState["investors"] : base.investors, contributions: Array.isArray(legacy.contributions) ? legacy.contributions as FundingState["contributions"] : base.contributions, capitalRemunerationEvents: Array.isArray(legacy.capitalRemunerationEvents) ? legacy.capitalRemunerationEvents as FundingState["capitalRemunerationEvents"] : base.capitalRemunerationEvents, fundingSources: Array.isArray(legacy.fundingSources) ? legacy.fundingSources as FundingState["fundingSources"] : base.fundingSources, fundingLedgerEntries: Array.isArray(legacy.fundingLedgerEntries) ? legacy.fundingLedgerEntries as FundingState["fundingLedgerEntries"] : base.fundingLedgerEntries, fundingContracts, contractFundingAllocations, fundingDivergences, treasuryIncomingReceipts: incoming, bankMovements, receiptBankReconciliations: links, treasuryDivergences: [], revenueDivergences: [], allocationReceiptShares, treasuryEntries: mappedEntries, auditEvents: [...(Array.isArray(legacy.auditEvents) ? legacy.auditEvents as FundingState["auditEvents"] : []), { id: "aud-migration-v4", entity: "SYSTEM", entityId: "demo", action: "CORRECAO_DOMINIO_V4", description: "Originações migradas para contratos; recebimentos migrados para uma identidade compartilhada entre Receita e Tesouraria.", date: new Date(0).toISOString(), demoUser: DEMO_USER }], reconciliations: Array.isArray(legacy.reconciliations) ? legacy.reconciliations as FundingState["reconciliations"] : base.reconciliations };
}

export class FundingRepository {
  private state: FundingState; private readonly listeners = new Set<() => void>();
  private readonly now: () => Date; private readonly idFactory: () => string;
  constructor(private readonly storage: StorageAdapter, options: RepositoryOptions = {}) { this.now = options.now ?? (() => new Date()); this.idFactory = options.idFactory ?? defaultIdFactory; this.state = this.load(); }
  private load(): FundingState { const current = this.storage.getItem(FUNDING_STORAGE_KEY); if (current) { try { const parsed: unknown = JSON.parse(current); if (isFundingState(parsed)) return parsed; } catch { /* restore below */ } } for (const key of [LEGACY_V3_STORAGE_KEY, LEGACY_V2_STORAGE_KEY, LEGACY_FUNDING_STORAGE_KEY]) { const raw = this.storage.getItem(key); if (!raw) continue; try { const migrated = migrateFundingState(JSON.parse(raw)); this.storage.setItem(FUNDING_STORAGE_KEY, JSON.stringify(migrated)); return migrated; } catch { /* try next source */ } } const initial = cloneDemoState(); this.storage.setItem(FUNDING_STORAGE_KEY, JSON.stringify(initial)); return initial; }
  private persist(): void { this.storage.setItem(FUNDING_STORAGE_KEY, JSON.stringify(this.state)); this.listeners.forEach((listener) => listener()); }
  private nextId(prefix: string): string { return `${prefix}-${this.idFactory()}`; }
  private timestamp(): string { return this.now().toISOString(); }
  private audit(entity: AuditEntity, entityId: string, action: string, description: string, user = DEMO_USER): void { this.state.auditEvents.push({ id: this.nextId("aud"), entity, entityId, action, description, date: this.timestamp(), demoUser: user }); }
  private assertMoney(...values: Cents[]): void { if (values.some((value) => cents(value) < 0n)) throw new RepositoryValidationError("Valores monetários não podem ser negativos."); }
  private findInvestor(id: string): Investor { const item = this.state.investors.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Investidor demonstrativo não encontrado."); return item; }
  private findContribution(id: string): Contribution { const item = this.state.contributions.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Aporte demonstrativo não encontrado."); return item; }
  private findRemuneration(id: string): CapitalRemunerationEvent { const item = this.state.capitalRemunerationEvents.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Remuneração demonstrativa não encontrada."); return item; }
  private findContract(id: string): FundingContract { const item = this.state.fundingContracts.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Contrato demonstrativo não encontrado."); return item; }
  private findIncoming(id: string): TreasuryIncomingReceipt { const item = this.state.treasuryIncomingReceipts.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Entrada esperada não encontrada."); return item; }

  subscribe(listener: () => void): () => void { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  getSnapshot(): FundingState { return structuredClone(this.state); }
  getRevenueRecords(): RevenueRecordView[] { return buildRevenueRecords(this.state).map((item) => structuredClone(item)); }
  getTreasurySummary(): TreasurySummary { return computeTreasurySummary(this.state, this.now()); }
  getHistoricalBalance(sourceId: string, date: string): Cents { return calculateHistoricalAvailableBalance(this.state, sourceId, date); }
  restoreDemoData(): void { this.state = cloneDemoState(); this.audit("SYSTEM", "demo", "RESTAURACAO", "Dados demonstrativos restaurados para a versão v4."); this.persist(); }
  updateRevenueColumnPreferences(preferences: RevenueColumnPreferences): RevenueColumnPreferences {
    this.state.revenueColumnPreferences = structuredClone(preferences);
    this.persist();
    return structuredClone(preferences);
  }

  createInvestor(input: InvestorInput): Investor { const timestamp = this.timestamp(); const item: Investor = { id: this.nextId("inv"), code: `INV-DEMO-${String(this.state.investors.length + 1).padStart(4, "0")}`, ...input, createdAt: timestamp, updatedAt: timestamp }; this.state.investors.push(item); this.audit("INVESTOR", item.id, "CRIACAO", `Investidor ${item.code} criado.`); this.persist(); return structuredClone(item); }
  updateInvestor(id: string, input: InvestorInput): Investor { const item = this.findInvestor(id); Object.assign(item, input, { updatedAt: this.timestamp() }); this.audit("INVESTOR", id, "EDICAO", `Investidor ${item.code} atualizado.`); this.persist(); return structuredClone(item); }
  createContribution(input: ContributionInput): Contribution { this.findInvestor(input.investorId); this.assertMoney(input.originalAmount, input.availableBalance, input.allocatedBalance); if (cents(input.availableBalance) + cents(input.allocatedBalance) > cents(input.originalAmount)) throw new RepositoryValidationError("A soma dos saldos não pode exceder o valor original."); const timestamp = this.timestamp(); const id = this.nextId("apt"); const item: Contribution = { id, code: `APT-DEMO-${String(this.state.contributions.length + 1).padStart(4, "0")}`, ...input, expectedMonthlyRemuneration: calculateCapitalRemuneration(input.originalAmount, input.monthlyRateBps), createdAt: timestamp, updatedAt: timestamp }; const sourceId = `src-${id}`; this.state.contributions.push(item); this.state.fundingSources.push({ id: sourceId, type: "INVESTOR_CONTRIBUTION", name: item.code, reference: id, historicalAvailableAmount: item.originalAmount, status: "ACTIVE" }); this.state.fundingLedgerEntries.push({ id: this.nextId("led"), fundingSourceId: sourceId, contributionId: id, type: "ENTRY", amount: item.originalAmount, date: item.startDate, reference: item.code }); this.state.treasuryEntries.push({ id: this.nextId("mov"), investorId: item.investorId, contributionId: id, type: "INVESTOR_CONTRIBUTION_RECEIVED", direction: "ENTRADA", amount: item.originalAmount, date: item.startDate, competence: monthOf(item.startDate), cashAccount: "Conta Caixa Demo 01", status: "CONFIRMADO", owner: DEMO_USER, reference: item.code, notes: "Entrada criada automaticamente.", createdAt: timestamp }); this.audit("CONTRIBUTION", id, "CRIACAO", `Aporte ${item.code} criado.`); this.persist(); return structuredClone(item); }
  updateContribution(id: string, input: ContributionInput): Contribution { this.assertMoney(input.originalAmount, input.availableBalance, input.allocatedBalance); const item = this.findContribution(id); if (cents(input.availableBalance) + cents(input.allocatedBalance) > cents(input.originalAmount)) throw new RepositoryValidationError("A soma dos saldos não pode exceder o valor original."); Object.assign(item, input, { expectedMonthlyRemuneration: calculateCapitalRemuneration(input.originalAmount, input.monthlyRateBps), updatedAt: this.timestamp() }); this.audit("CONTRIBUTION", id, "EDICAO", `Aporte ${item.code} atualizado.`); this.persist(); return structuredClone(item); }
  setContributionStatus(id: string, status: Contribution["status"]): Contribution { const item = this.findContribution(id); item.status = status; item.updatedAt = this.timestamp(); this.audit("CONTRIBUTION", id, "MUDANCA_STATUS", `Aporte ${item.code} alterado para ${status}.`); this.persist(); return structuredClone(item); }

  createCapitalRemuneration(input: CapitalRemunerationInput): CapitalRemunerationEvent { const contribution = this.findContribution(input.contributionId); if (contribution.investorId !== input.investorId) throw new RepositoryValidationError("O aporte não pertence ao investidor selecionado."); this.assertMoney(input.informedPjrAmount); const gross = calculateCapitalRemuneration(contribution.originalAmount, contribution.monthlyRateBps); if (cents(input.informedPjrAmount) > cents(gross)) throw new RepositoryValidationError("O PJR informado não pode exceder o valor bruto."); const item: CapitalRemunerationEvent = { id: this.nextId("rem"), ...input, originalContributionAmount: contribution.originalAmount, monthlyRateBps: contribution.monthlyRateBps, grossAmount: gross, netAmount: centsString(cents(gross) - cents(input.informedPjrAmount)), history: [] }; this.state.capitalRemunerationEvents.push(item); this.audit("CAPITAL_REMUNERATION", item.id, "CRIACAO", `Remuneração ${item.competence} criada.`); this.persist(); return structuredClone(item); }
  payCapitalRemuneration(id: string, details: Omit<PaymentBatchInput, "remunerationIds">): CapitalRemunerationEvent { const item = this.findRemuneration(id); if (["PAGA", "REINVESTIDA", "QUITADA", "CANCELADA"].includes(item.status)) throw new RepositoryValidationError("Evento não disponível para pagamento."); item.status = "PAGA"; item.paymentDate = details.date; item.settlementMethod = "BANK_TRANSFER"; item.cashAccount = details.cashAccount; item.history.push({ id: this.nextId("remh"), action: "PAGAMENTO", description: `Pagamento pela conta ${details.cashAccount}.`, date: this.timestamp(), responsibleUser: details.owner }); this.state.treasuryEntries.push({ id: this.nextId("mov"), investorId: item.investorId, contributionId: item.contributionId, capitalRemunerationEventId: id, type: "CAPITAL_REMUNERATION_PAID", direction: "SAIDA", amount: item.netAmount, date: details.date, competence: item.competence, cashAccount: details.cashAccount, status: "CONFIRMADO", owner: details.owner, reference: `REM:${id}`, notes: details.notes, createdAt: this.timestamp() }); if (cents(item.informedPjrAmount) > 0n) this.state.treasuryEntries.push({ id: this.nextId("mov"), investorId: item.investorId, contributionId: item.contributionId, capitalRemunerationEventId: id, type: "PJR_PAYMENT", direction: "SAIDA", amount: item.informedPjrAmount, date: details.date, competence: item.competence, cashAccount: details.cashAccount, status: "CONFIRMADO", owner: details.owner, reference: `PJR:${id}`, notes: "Valor informado; regra definitiva fora do escopo.", createdAt: this.timestamp() }); this.audit("CAPITAL_REMUNERATION", id, "PAGAMENTO", "Remuneração paga e saída de tesouraria criada.", details.owner); this.persist(); return structuredClone(item); }
  payCapitalRemunerations(input: PaymentBatchInput): CapitalRemunerationEvent[] { return input.remunerationIds.map((id) => this.payCapitalRemuneration(id, input)); }
  reinvestCapitalRemuneration(id: string, details: { date: string; owner: string; notes: string; target: "SAME_CONTRIBUTION" | "NEW_CONTRIBUTION" }): CapitalRemunerationEvent { const item = this.findRemuneration(id); if (["PAGA", "REINVESTIDA", "QUITADA", "CANCELADA"].includes(item.status)) throw new RepositoryValidationError("Evento não disponível para reinvestimento."); const contribution = this.findContribution(item.contributionId); let targetContributionId = contribution.id; if (details.target === "SAME_CONTRIBUTION") { contribution.availableBalance = centsString(cents(contribution.availableBalance) + cents(item.netAmount)); contribution.updatedAt = this.timestamp(); } else { const createdId = this.nextId("apt"); const timestamp = this.timestamp(); const created: Contribution = { id: createdId, investorId: item.investorId, code: `APT-DEMO-${String(this.state.contributions.length + 1).padStart(4, "0")}`, originalAmount: item.netAmount, availableBalance: item.netAmount, allocatedBalance: "0", startDate: details.date, endDate: contribution.endDate, monthlyRateBps: contribution.monthlyRateBps, expectedMonthlyRemuneration: calculateCapitalRemuneration(item.netAmount, contribution.monthlyRateBps), status: "ATIVO", notes: `Criado por reinvestimento de ${id}.`, createdAt: timestamp, updatedAt: timestamp }; targetContributionId = created.id; this.state.contributions.push(created); this.state.fundingSources.push({ id: `src-${created.id}`, type: "INVESTOR_CONTRIBUTION", name: created.code, reference: created.id, historicalAvailableAmount: created.originalAmount, status: "ACTIVE" }); this.audit("CONTRIBUTION", created.id, "CRIACAO_POR_REINVESTIMENTO", `Novo aporte ${created.code} criado sem movimento bancário.`, details.owner); } const source = this.state.fundingSources.find((value) => value.reference === targetContributionId); if (source) this.state.fundingLedgerEntries.push({ id: this.nextId("led"), fundingSourceId: source.id, contributionId: targetContributionId, type: "REINTEGRATION", amount: item.netAmount, date: details.date, reference: `REINV:${id}` }); item.status = "REINVESTIDA"; item.paymentDate = details.date; item.settlementMethod = "REINVESTMENT"; item.history.push({ id: this.nextId("remh"), action: "REINVESTIMENTO", description: `Reinvestido em ${targetContributionId}, sem saída bancária.`, date: this.timestamp(), responsibleUser: details.owner }); this.state.treasuryEntries.push({ id: this.nextId("mov"), investorId: item.investorId, contributionId: targetContributionId, capitalRemunerationEventId: id, type: "REMUNERATION_REINVESTED", direction: "TRANSFERENCIA_INTERNA", amount: item.netAmount, date: details.date, competence: item.competence, cashAccount: "Conta Virtual de Reinvestimento", status: "CONFIRMADO", owner: details.owner, reference: `REINV:${id}`, notes: details.notes, createdAt: this.timestamp() }); this.audit("CAPITAL_REMUNERATION", id, "REINVESTIMENTO", "Remuneração reinvestida sem saída bancária.", details.owner); this.persist(); return structuredClone(item); }

  private openFundingDivergence(contract: FundingContract, type: FundingDivergenceType, expected: Cents, identified: Cents, description: string): FundingDivergence { const item: FundingDivergence = { id: this.nextId("divg"), fundingContractId: contract.id, type, expectedAmount: expected, identifiedAmount: identified, differenceAmount: centsString(absolute(cents(expected) - cents(identified))), description, status: "OPEN", createdAt: this.timestamp() }; this.state.fundingDivergences.push(item); this.audit("DIVERGENCE", item.id, "ABERTURA", description); return item; }
  private buildAllocations(contract: FundingContract, inputs: ContractFundingAllocationInput[], validFrom: string): ContractFundingAllocation[] { return inputs.map((input) => { this.assertMoney(input.amount); const source = input.fundingSourceId ? this.state.fundingSources.find((value) => value.id === input.fundingSourceId) : undefined; const historical = source ? calculateHistoricalAvailableBalance(this.state, source.id, contract.operationDate) : "0"; const insufficient = input.fundingSourceType === "INVESTOR_CONTRIBUTION" && cents(input.amount) > cents(historical); const unidentified = input.fundingSourceType === "UNIDENTIFIED_SOURCE"; return { id: this.nextId("alloc"), fundingContractId: contract.id, ...input, validFrom, historicalAvailableBalance: historical, validationStatus: insufficient || unidentified ? "DIVERGENT" : "VALID", divergenceReason: insufficient ? "Saldo histórico insuficiente na data da operação." : unidentified ? "Fonte pendente de identificação." : undefined }; }); }
  private validateContractFunding(contract: FundingContract, allocations: ContractFundingAllocation[]): void { const total = sumCents(allocations.map((item) => item.amount)); allocations.filter((item) => item.fundingSourceType === "INVESTOR_CONTRIBUTION" && cents(item.amount) > cents(item.historicalAvailableBalance)).forEach((item) => this.openFundingDivergence(contract, "INSUFFICIENT_INVESTOR_BALANCE", item.amount, item.historicalAvailableBalance, `Saldo histórico insuficiente para ${item.contributionId ?? "aporte"}.`)); const bySource = new Map<string, ContractFundingAllocation[]>(); allocations.forEach((item) => { if (item.fundingSourceId) bySource.set(item.fundingSourceId, [...(bySource.get(item.fundingSourceId) ?? []), item]); }); bySource.forEach((items) => { const used = cents(sumCents(items.map((item) => item.amount))); const historical = cents(items[0].historicalAvailableBalance); if (items.length > 1) this.openFundingDivergence(contract, "DUPLICATED_CAPITAL_USAGE", centsString(used), items[0].historicalAvailableBalance, "A mesma fonte foi informada mais de uma vez na composição."); if (items[0].fundingSourceType === "INVESTOR_CONTRIBUTION" && used > historical && !items.some((item) => cents(item.amount) > historical)) this.openFundingDivergence(contract, "INSUFFICIENT_INVESTOR_BALANCE", centsString(used), centsString(historical), "O total alocado da fonte excede seu saldo histórico."); }); if (cents(total) !== cents(contract.releasedAmount)) { this.openFundingDivergence(contract, "FUNDING_TOTAL_MISMATCH", contract.releasedAmount, total, "O funding informado difere do valor liberado."); if (cents(total) < cents(contract.releasedAmount) && !allocations.some((item) => item.fundingSourceType === "REMO_OWN_CAPITAL")) this.openFundingDivergence(contract, "MISSING_REMO_CAPITAL", contract.releasedAmount, total, "Possível complemento com capital próprio REMO ainda não informado."); } const unidentified = allocations.filter((item) => item.fundingSourceType === "UNIDENTIFIED_SOURCE").reduce((sum, item) => sum + cents(item.amount), 0n); if (unidentified > 0n) this.openFundingDivergence(contract, "UNIDENTIFIED_FUNDING_SOURCE", centsString(unidentified), "0", "Há fonte de funding pendente de identificação."); const hasOpen = this.state.fundingDivergences.some((item) => item.fundingContractId === contract.id && ["OPEN", "IN_REVIEW"].includes(item.status)); contract.fundingValidationStatus = hasOpen ? "DIVERGENT" : "VALID"; contract.status = hasOpen ? "FUNDING_DIVERGENT" : "FUNDED"; }
  createContract(input: FundingContractInput, allocationInputs: ContractFundingAllocationInput[]): FundingContract { this.assertMoney(input.principalAmount, input.financedAmount, input.releasedAmount, input.installmentAmount); const timestamp = this.timestamp(); const contract: FundingContract = { id: this.nextId("contract"), ...input, status: "DRAFT", fundingValidationStatus: "PENDING", createdAt: timestamp, updatedAt: timestamp }; this.state.fundingContracts.push(contract); const allocations = this.buildAllocations(contract, allocationInputs, contract.operationDate); this.state.contractFundingAllocations.push(...allocations); this.validateContractFunding(contract, allocations); this.state.treasuryEntries.push({ id: this.nextId("mov"), fundingContractId: contract.id, type: "CAPITAL_ALLOCATED", direction: "TRANSFERENCIA_INTERNA", amount: sumCents(allocations.map((item) => item.amount)), date: contract.operationDate, competence: monthOf(contract.operationDate), cashAccount: "Reserva contábil", status: "CONFIRMADO", owner: contract.responsibleUser, reference: contract.contractCode, notes: "Reserva contábil; não representa entrada nem saída bancária.", createdAt: timestamp }); this.audit("CONTRACT", contract.id, "CRIACAO", `Contrato ${contract.contractCode} criado.`); this.audit("FUNDING_ALLOCATION", contract.id, "COMPOSICAO", `${allocations.length} fonte(s) registrada(s).`); this.persist(); return structuredClone(contract); }
  reviseContractFunding(contractId: string, inputs: ContractFundingAllocationInput[], responsible: string): FundingContract { const contract = this.findContract(contractId); const revisedAt = this.timestamp(); const previous = currentAllocations(this.state, contractId); const previousTotal = sumCents(previous.map((item) => item.amount)); previous.forEach((item) => { item.supersededAt = revisedAt; item.validUntil = revisedAt; item.validationStatus = "CORRECTION_REQUIRED"; }); const allocations = this.buildAllocations(contract, inputs, revisedAt); allocations.forEach((item, index) => { item.revisedFromId = previous[index]?.id; }); this.state.contractFundingAllocations.push(...allocations); this.state.treasuryEntries.push({ id: this.nextId("mov"), fundingContractId: contract.id, type: "CAPITAL_DEALLOCATED", direction: "TRANSFERENCIA_INTERNA", amount: previousTotal, date: dateOnly(this.now()), competence: monthOf(dateOnly(this.now())), cashAccount: "Reserva contábil", status: "CONFIRMADO", owner: responsible, reference: `CORRECAO:${contract.contractCode}`, notes: "Versão anterior desalocada e preservada.", createdAt: revisedAt }); this.state.treasuryEntries.push({ id: this.nextId("mov"), fundingContractId: contract.id, type: "CAPITAL_ALLOCATED", direction: "TRANSFERENCIA_INTERNA", amount: sumCents(allocations.map((item) => item.amount)), date: dateOnly(this.now()), competence: monthOf(dateOnly(this.now())), cashAccount: "Reserva contábil", status: "CONFIRMADO", owner: responsible, reference: `REVISAO:${contract.contractCode}`, notes: "Nova versão da composição.", createdAt: revisedAt }); this.state.fundingDivergences.filter((item) => item.fundingContractId === contractId && ["OPEN", "IN_REVIEW"].includes(item.status)).forEach((item) => { item.status = "RESOLVED"; item.resolutionType = "CORRECT_ALLOCATION"; item.resolutionNotes = "Composição substituída; versão anterior preservada."; item.resolvedAt = revisedAt; item.resolvedBy = responsible; }); this.validateContractFunding(contract, allocations); contract.updatedAt = revisedAt; this.audit("FUNDING_ALLOCATION", contractId, "CORRECAO", "Composição corrigida sem apagar a versão anterior.", responsible); this.persist(); return structuredClone(contract); }
  confirmContractRelease(contractId: string, input: ContractReleaseInput): TreasuryEntry { const contract = this.findContract(contractId); const existing = this.state.treasuryEntries.find((item) => item.fundingContractId === contractId && item.type === "LOAN_RELEASE" && item.status === "CONFIRMADO"); if (existing) return structuredClone(existing); const entry: TreasuryEntry = { id: this.nextId("mov"), fundingContractId: contractId, type: "LOAN_RELEASE", direction: "SAIDA", amount: contract.releasedAmount, date: input.date, competence: monthOf(input.date), cashAccount: input.cashAccount, status: "CONFIRMADO", owner: input.owner, reference: input.transactionReference, notes: input.notes, createdAt: this.timestamp() }; this.state.treasuryEntries.push(entry); contract.status = contract.fundingValidationStatus === "VALID" ? "RELEASED" : "FUNDING_DIVERGENT"; contract.releaseDate = input.date; contract.updatedAt = this.timestamp(); this.audit("CONTRACT", contractId, "LIBERACAO", "Liberação registrada exclusivamente como saída de tesouraria.", input.owner); this.persist(); return structuredClone(entry); }
  resolveFundingDivergence(id: string, resolutionType: DivergenceResolutionType, notes: string, responsible: string): FundingDivergence { const item = this.state.fundingDivergences.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Divergência não encontrada."); item.status = resolutionType === "JUSTIFIED_EXCEPTION" ? "JUSTIFIED_EXCEPTION" : "RESOLVED"; item.resolutionType = resolutionType; item.resolutionNotes = notes; item.resolvedAt = this.timestamp(); item.resolvedBy = responsible; this.audit("DIVERGENCE", id, "RESOLUCAO", "Divergência de funding encerrada sem exclusão.", responsible); this.persist(); return structuredClone(item); }

  private openRevenueDivergence(receipt: TreasuryIncomingReceipt, type: RevenueDivergenceType, expected: Cents, actual: Cents, description: string, sourceTreasuryDivergenceId?: string): RevenueDivergence {
    const existing = this.state.revenueDivergences.find((item) => item.incomingReceiptId === receipt.id && item.type === type && ["OPEN", "IN_REVIEW"].includes(item.status));
    if (existing) {
      existing.expectedAmount = expected; existing.actualAmount = actual;
      existing.differenceAmount = absolute(cents(expected) - cents(actual)).toString();
      existing.description = description; existing.updatedAt = this.timestamp();
      if (sourceTreasuryDivergenceId) existing.sourceTreasuryDivergenceId = sourceTreasuryDivergenceId;
      return existing;
    }
    const timestamp = this.timestamp();
    const item: RevenueDivergence = {
      id: this.nextId("revdiv"), incomingReceiptId: receipt.id, type, expectedAmount: expected,
      actualAmount: actual, differenceAmount: absolute(cents(expected) - cents(actual)).toString(),
      description, status: "OPEN", sourceTreasuryDivergenceId, createdAt: timestamp, updatedAt: timestamp,
    };
    this.state.revenueDivergences.push(item);
    this.audit("DIVERGENCE", item.id, "ABERTURA_RECEITA", description, receipt.responsibleUser);
    return item;
  }

  private refreshComponentDivergence(receipt: TreasuryIncomingReceipt): void {
    const mismatch = deriveComponentStatus(receipt) === "COMPONENTS_MISMATCH";
    const open = this.state.revenueDivergences.filter((item) => item.incomingReceiptId === receipt.id && item.type === "RECEIPT_COMPONENT_MISMATCH" && ["OPEN", "IN_REVIEW"].includes(item.status));
    if (mismatch) {
      this.openRevenueDivergence(receipt, "RECEIPT_COMPONENT_MISMATCH", receipt.paidAmountFromOperationalSource, calculateApuratedAmount(receipt), "Os componentes informados não fecham o valor pago operacional.");
    } else {
      open.forEach((item) => { item.status = "RESOLVED"; item.resolutionNotes = "Componentes passaram a fechar sem alteração silenciosa dos valores."; item.resolvedAt = this.timestamp(); item.resolvedBy = receipt.responsibleUser; item.updatedAt = this.timestamp(); });
    }
  }

  createIncomingReceipt(input: TreasuryIncomingReceiptInput): TreasuryIncomingReceipt {
    this.assertMoney(input.expectedAmount, input.paidAmountFromOperationalSource, input.principalAmount, input.interestAmount, input.iofAmount, input.penaltyAmount, input.discountAmount, input.lossAmount);
    const duplicate = this.state.treasuryIncomingReceipts.find((item) => item.sourceReference === input.sourceReference
      || (item.contractCode === input.contractCode && item.installmentNumber === input.installmentNumber && item.dueDate === input.dueDate));
    if (duplicate) {
      this.openRevenueDivergence(duplicate, "DUPLICATED_RECEIPT", duplicate.paidAmountFromOperationalSource, input.paidAmountFromOperationalSource, "Tentativa de criar uma segunda ocorrência para a mesma baixa operacional; o registro central existente foi preservado.");
      this.audit("REVENUE", duplicate.id, "DUPLICIDADE_BLOQUEADA", "Recebimento duplicado não foi criado.", input.responsibleUser);
      this.persist();
      return structuredClone(duplicate);
    }
    const timestamp = this.timestamp(); const writtenOff = input.operationalStatus === "WRITTEN_OFF";
    const item: TreasuryIncomingReceipt = { id: this.nextId("incoming"), ...input, bankValidationStatus: "PENDING", reconciliationStatus: "PENDING", status: writtenOff ? "WAITING_BANK_VALIDATION" : "WAITING_OPERATIONAL_WRITE_OFF", createdAt: timestamp, updatedAt: timestamp };
    this.state.treasuryIncomingReceipts.push(item);
    this.refreshComponentDivergence(item);
    this.audit("INCOMING_RECEIPT", item.id, writtenOff ? "BAIXA_OPERACIONAL" : "ENTRADA_ESPERADA", writtenOff ? "Baixa operacional recebida; entrada aguarda validação bancária." : "Entrada aguardando baixa operacional.", item.responsibleUser);
    this.persist(); return structuredClone(item);
  }
  registerOperationalWriteOff(id: string, details: { date: string; paidAmount: Cents; principalAmount: Cents; interestAmount: Cents; iofAmount: Cents; penaltyAmount: Cents; discountAmount: Cents; lossAmount: Cents; responsible: string }): TreasuryIncomingReceipt {
    const item = this.findIncoming(id);
    this.assertMoney(details.paidAmount, details.principalAmount, details.interestAmount, details.iofAmount, details.penaltyAmount, details.discountAmount, details.lossAmount);
    if (["REVERSED", "CANCELLED"].includes(item.status)) {
      this.openRevenueDivergence(item, "OPERATIONAL_STATUS_CONFLICT", item.paidAmountFromOperationalSource, details.paidAmount, "Tentativa de baixa operacional em recebimento estornado ou cancelado.");
      this.persist();
      throw new RepositoryValidationError("O estado atual do recebimento conflita com uma nova baixa operacional.");
    }
    Object.assign(item, { operationalWriteOffDate: details.date, paidAmountFromOperationalSource: details.paidAmount, principalAmount: details.principalAmount, interestAmount: details.interestAmount, iofAmount: details.iofAmount, penaltyAmount: details.penaltyAmount, discountAmount: details.discountAmount, lossAmount: details.lossAmount, operationalStatus: "WRITTEN_OFF", status: "WAITING_BANK_VALIDATION", updatedAt: this.timestamp() });
    this.refreshComponentDivergence(item);
    this.audit("INCOMING_RECEIPT", id, "BAIXA_OPERACIONAL", "Baixa operacional registrada; nenhuma entrada de caixa foi criada ainda.", details.responsible);
    this.persist(); return structuredClone(item);
  }

  private openTreasuryDivergence(receipt: TreasuryIncomingReceipt, type: TreasuryDivergenceType, reconciled: Cents, description: string): TreasuryDivergence {
    const target = cents(receipt.paidAmountFromOperationalSource) > 0n ? receipt.paidAmountFromOperationalSource : receipt.expectedAmount;
    let item = this.state.treasuryDivergences.find((value) => value.incomingReceiptId === receipt.id && value.type === type && ["OPEN", "IN_REVIEW"].includes(value.status));
    if (item) {
      item.reconciledAmount = reconciled; item.differenceAmount = centsString(absolute(cents(target) - cents(reconciled))); item.description = description;
    } else {
      item = { id: this.nextId("tdiv"), incomingReceiptId: receipt.id, type, expectedAmount: target, reconciledAmount: reconciled, differenceAmount: centsString(absolute(cents(target) - cents(reconciled))), description, status: "OPEN", createdAt: this.timestamp() };
      this.state.treasuryDivergences.push(item); this.audit("DIVERGENCE", item.id, "ABERTURA", description);
    }
    this.openRevenueDivergence(receipt, type, target, reconciled, description, item.id);
    return item;
  }

  private calculateIncomingShares(receipt: TreasuryIncomingReceipt): void {
    if (this.state.allocationReceiptShares.some((item) => item.incomingReceiptId === receipt.id && item.status !== "REVERSED")) return;
    const contract = receipt.fundingContractId ? this.state.fundingContracts.find((item) => item.id === receipt.fundingContractId) : this.state.fundingContracts.find((item) => item.contractCode === receipt.contractCode);
    const referenceDate = receipt.operationalWriteOffDate ?? receipt.dueDate;
    const allocations = contract ? getContractAllocationsAt(this.state, contract.id, referenceDate) : [];
    if (!contract || allocations.length === 0) {
      this.openRevenueDivergence(receipt, "FUNDING_COMPOSITION_NOT_FOUND", "1", "0", `Não existe composição de funding válida em ${referenceDate}.`);
      return;
    }
    const weights = allocations.map((item) => item.amount);
    const principal = proportionalSplit(receipt.principalAmount, weights); const interest = proportionalSplit(receipt.interestAmount, weights);
    const penalty = proportionalSplit(receipt.penaltyAmount, weights); const discount = proportionalSplit(receipt.discountAmount, weights); const loss = proportionalSplit(receipt.lossAmount, weights);
    const total = cents(sumCents(weights));
    const shares: AllocationReceiptShare[] = allocations.map((allocation, index) => ({
      id: this.nextId("share"), incomingReceiptId: receipt.id, contractFundingAllocationId: allocation.id,
      fundingSourceType: allocation.fundingSourceType, investorId: allocation.investorId, contributionId: allocation.contributionId,
      allocationBps: total === 0n ? 0 : Number(cents(allocation.amount) * 10_000n / total),
      principalShare: principal[index], interestShare: interest[index], iofShare: "0", penaltyShare: penalty[index],
      discountShare: discount[index], lossShare: loss[index], iofDestinationStatus: "RULE_TO_CONFIRM", status: "CALCULATED", calculatedAt: this.timestamp(),
    }));
    this.state.allocationReceiptShares.push(...shares);
    const distributed = shares.reduce((sum, item) => sum + cents(item.principalShare) + cents(item.interestShare) + cents(item.penaltyShare) - cents(item.discountShare) - cents(item.lossShare), 0n);
    const distributable = cents(receipt.principalAmount) + cents(receipt.interestAmount) + cents(receipt.penaltyAmount) - cents(receipt.discountAmount) - cents(receipt.lossAmount);
    if (distributed !== distributable) this.openRevenueDivergence(receipt, "ALLOCATION_TOTAL_MISMATCH", distributable.toString(), distributed.toString(), "O total distribuído entre as fontes não fecha os componentes rateáveis.");
    this.audit("REVENUE", receipt.id, "RATEIO", `Rateio calculado com a composição válida em ${referenceDate}; IOF mantido fora da atribuição até confirmação da regra.`);
  }

  private refreshIncomingStatus(receipt: TreasuryIncomingReceipt): void {
    const links = this.state.receiptBankReconciliations.filter((item) => item.incomingReceiptId === receipt.id && item.status === "ACTIVE");
    const reconciled = links.reduce((sum, item) => sum + cents(item.amount), 0n);
    const target = cents(receipt.paidAmountFromOperationalSource) > 0n ? cents(receipt.paidAmountFromOperationalSource) : cents(receipt.expectedAmount);
    receipt.updatedAt = this.timestamp();
    if (reconciled === target) {
      receipt.status = "VALIDATED"; receipt.bankValidationStatus = "VALIDATED"; receipt.reconciliationStatus = "RECONCILED";
      this.state.treasuryDivergences.filter((item) => item.incomingReceiptId === receipt.id && ["OPEN", "IN_REVIEW"].includes(item.status)).forEach((item) => { item.status = "RESOLVED"; item.resolutionNotes = "Soma conciliada alcançou exatamente o valor esperado."; item.resolvedAt = this.timestamp(); item.resolvedBy = DEMO_USER; });
      this.state.revenueDivergences.filter((item) => item.incomingReceiptId === receipt.id && ["BANK_AMOUNT_MISMATCH", "BANK_MOVEMENT_NOT_FOUND", "PARTIAL_PAYMENT"].includes(item.type) && ["OPEN", "IN_REVIEW"].includes(item.status)).forEach((item) => { item.status = "RESOLVED"; item.resolutionNotes = "Soma bancária conciliada exatamente."; item.resolvedAt = this.timestamp(); item.resolvedBy = DEMO_USER; item.updatedAt = this.timestamp(); });
      this.calculateIncomingShares(receipt);
    } else if (reconciled > 0n && reconciled < target) {
      receipt.status = "PARTIALLY_VALIDATED"; receipt.bankValidationStatus = "VALUE_MISMATCH"; receipt.reconciliationStatus = "PARTIAL";
      this.openTreasuryDivergence(receipt, "BANK_AMOUNT_MISMATCH", reconciled.toString(), "Pagamento parcialmente localizado; permanece saldo não conciliado.");
      this.openRevenueDivergence(receipt, "PARTIAL_PAYMENT", target.toString(), reconciled.toString(), "Recebimento bancário parcial.");
    } else if (reconciled > target) {
      receipt.status = "BANK_VALUE_MISMATCH"; receipt.bankValidationStatus = "VALUE_MISMATCH"; receipt.reconciliationStatus = "DIVERGENT";
      this.openTreasuryDivergence(receipt, "BANK_AMOUNT_MISMATCH", reconciled.toString(), "A soma conciliada excede o valor esperado da baixa.");
    } else {
      receipt.status = "WAITING_BANK_VALIDATION"; receipt.bankValidationStatus = "PENDING"; receipt.reconciliationStatus = "PENDING";
    }
  }
  reconcileBankMovement(input: BankMovementInput, links: ReceiptBankReconciliationInput[]): BankMovement {
    this.assertMoney(input.amount, ...links.map((item) => item.amount));
    if (links.length === 0) throw new RepositoryValidationError("Selecione ao menos uma entrada esperada.");
    const linkedTotal = links.reduce((sum, item) => sum + cents(item.amount), 0n);
    if (input.status === "FOUND" && (cents(input.amount) <= 0n || linkedTotal <= 0n)) {
      throw new RepositoryValidationError("Informe um movimento positivo e ao menos uma associação com valor.");
    }
    if (input.status === "FOUND" && linkedTotal > cents(input.amount)) {
      throw new RepositoryValidationError("A soma associada não pode exceder o movimento bancário.");
    }
    const duplicatedMovement = input.status === "FOUND" && this.state.bankMovements.some((item) => item.status !== "REVERSED"
      && item.bankAccountId === input.bankAccountId && item.movementDate === input.movementDate
      && item.amount === input.amount && item.transactionReference === input.transactionReference);
    if (duplicatedMovement) {
      links.forEach((link) => {
        const receipt = this.findIncoming(link.incomingReceiptId);
        this.openRevenueDivergence(receipt, "DUPLICATED_RECEIPT", input.amount, input.amount, "O mesmo movimento bancário já foi registrado; nenhuma segunda entrada de caixa foi criada.");
      });
      this.persist();
      throw new RepositoryValidationError("Este movimento bancário já foi registrado.");
    }

    const movement: BankMovement = { id: this.nextId("bank"), ...input };
    this.state.bankMovements.push(movement);
    if (input.status === "NOT_FOUND") {
      links.forEach((link) => {
        const receipt = this.findIncoming(link.incomingReceiptId);
        this.state.receiptBankReconciliations.push({ id: this.nextId("link"), incomingReceiptId: link.incomingReceiptId, bankMovementId: movement.id, amount: "0", status: "ACTIVE", confirmedBy: input.checkedBy, confirmedAt: input.checkedAt, notes: link.notes });
        receipt.status = "BANK_MOVEMENT_NOT_FOUND";
        receipt.bankValidationStatus = "MOVEMENT_NOT_FOUND";
        receipt.reconciliationStatus = "DIVERGENT";
        receipt.updatedAt = this.timestamp();
        this.openTreasuryDivergence(receipt, "BANK_MOVEMENT_NOT_FOUND", "0", "Movimento bancário não encontrado na conferência manual.");
      });
    } else {
      const reconciliations: ReceiptBankReconciliation[] = links
        .filter((link) => cents(link.amount) > 0n)
        .map((link) => ({
          id: this.nextId("link"),
          incomingReceiptId: link.incomingReceiptId,
          bankMovementId: movement.id,
          amount: link.amount,
          status: "ACTIVE",
          confirmedBy: input.checkedBy,
          confirmedAt: input.checkedAt,
          notes: link.notes,
        }));
      this.state.receiptBankReconciliations.push(...reconciliations);
      this.state.treasuryEntries.push({
        id: this.nextId("mov"),
        bankMovementId: movement.id,
        incomingReceiptId: reconciliations.length === 1 ? reconciliations[0].incomingReceiptId : undefined,
        type: "PMT_RECEIVED",
        direction: "ENTRADA",
        amount: input.amount,
        date: input.movementDate,
        competence: monthOf(input.movementDate),
        cashAccount: input.bankAccountId,
        status: "CONFIRMADO",
        owner: input.checkedBy,
        reference: input.transactionReference,
        notes: "Uma entrada de caixa por movimento bancário; principal, juros e IOF não são duplicados.",
        createdAt: input.checkedAt,
      });
      new Set(reconciliations.map((item) => item.incomingReceiptId)).forEach((id) => this.refreshIncomingStatus(this.findIncoming(id)));
    }
    this.audit("BANK_MOVEMENT", movement.id, "CONFERENCIA_MANUAL", input.status === "FOUND" ? "Movimento encontrado e associado explicitamente." : "Tentativa registrada como movimento não encontrado.", input.checkedBy);
    this.persist();
    return structuredClone(movement);
  }
  reverseBankMovement(id: string, details: { date: string; owner: string; notes: string }): BankMovement {
    const movement = this.state.bankMovements.find((item) => item.id === id);
    if (!movement || movement.status !== "FOUND") throw new RepositoryValidationError("Somente movimentos encontrados podem ser estornados.");
    movement.status = "REVERSED";
    const affected = this.state.receiptBankReconciliations.filter((item) => item.bankMovementId === id && item.status === "ACTIVE");
    affected.forEach((item) => { item.status = "REVERSED"; });
    this.state.treasuryEntries.filter((item) => item.bankMovementId === id && item.status === "CONFIRMADO").forEach((item) => {
      item.status = "ESTORNADO";
      this.state.treasuryEntries.push({ id: this.nextId("mov"), bankMovementId: id, type: "REVERSAL_OUT", direction: "SAIDA", amount: item.amount, date: details.date, competence: monthOf(details.date), cashAccount: item.cashAccount, status: "CONFIRMADO", owner: details.owner, reference: `ESTORNO:${item.reference}`, notes: details.notes, createdAt: this.timestamp() });
    });
    new Set(affected.map((item) => item.incomingReceiptId)).forEach((receiptId) => {
      const receipt = this.findIncoming(receiptId);
      const shares = this.state.allocationReceiptShares.filter((item) => item.incomingReceiptId === receiptId && item.status !== "REVERSED");
      if (shares.length > 0) {
        shares.forEach((item) => { item.status = "REVERSED"; });
        this.openRevenueDivergence(receipt, "REVERSED_AFTER_ALLOCATION", receipt.paidAmountFromOperationalSource, "0", "Recebimento estornado depois do cálculo do rateio; histórico preservado.");
      }
      this.refreshIncomingStatus(receipt);
      if (!this.state.receiptBankReconciliations.some((item) => item.incomingReceiptId === receiptId && item.status === "ACTIVE")) {
        receipt.status = "REVERSED"; receipt.bankValidationStatus = "PENDING"; receipt.reconciliationStatus = "REVERSED";
      }
    });
    this.audit("BANK_MOVEMENT", id, "ESTORNO", "Movimento, associações e rateios preservados; contrapartida criada.", details.owner);
    this.persist(); return structuredClone(movement);
  }
  resolveTreasuryDivergence(id: string, notes: string, responsible: string): TreasuryDivergence { const item = this.state.treasuryDivergences.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Divergência de tesouraria não encontrada."); item.status = "RESOLVED"; item.resolutionNotes = notes; item.resolvedAt = this.timestamp(); item.resolvedBy = responsible; this.audit("DIVERGENCE", id, "RESOLUCAO", "Divergência de entrada encerrada sem exclusão.", responsible); this.persist(); return structuredClone(item); }

  recalculateRevenueAllocation(receiptId: string, responsible: string): AllocationReceiptShare[] {
    const receipt = this.findIncoming(receiptId);
    if (receipt.bankValidationStatus !== "VALIDATED") throw new RepositoryValidationError("O rateio só pode ser recalculado após a validação bancária.");
    this.state.allocationReceiptShares.filter((item) => item.incomingReceiptId === receiptId && item.status !== "REVERSED").forEach((item) => { item.status = "REVERSED"; });
    this.calculateIncomingShares(receipt);
    this.audit("REVENUE", receiptId, "RECALCULO_RATEIO", "Rateio recalculado sem apagar versões anteriores.", responsible);
    this.persist();
    return structuredClone(this.state.allocationReceiptShares.filter((item) => item.incomingReceiptId === receiptId && item.status !== "REVERSED"));
  }

  confirmRevenueAllocation(receiptId: string, responsible: string): AllocationReceiptShare[] {
    const receipt = this.findIncoming(receiptId);
    const shares = this.state.allocationReceiptShares.filter((item) => item.incomingReceiptId === receiptId && item.status !== "REVERSED");
    if (shares.length === 0) throw new RepositoryValidationError("Não há rateio calculado para confirmar.");
    if (this.state.revenueDivergences.some((item) => item.incomingReceiptId === receiptId && ["FUNDING_COMPOSITION_NOT_FOUND", "ALLOCATION_TOTAL_MISMATCH"].includes(item.type) && ["OPEN", "IN_REVIEW"].includes(item.status))) throw new RepositoryValidationError("Resolva as divergências do rateio antes da confirmação.");
    shares.forEach((item) => { item.status = "CONFIRMED"; });
    this.audit("REVENUE", receipt.id, "CONFIRMACAO_RATEIO", "Rateio demonstrativo confirmado.", responsible);
    this.persist(); return structuredClone(shares);
  }

  updateRevenueDivergence(id: string, action: RevenueDivergenceAction, notes: string, responsible: string): RevenueDivergence {
    const item = this.state.revenueDivergences.find((value) => value.id === id);
    if (!item) throw new RepositoryValidationError("Divergência de Receita não encontrada.");
    const timestamp = this.timestamp();
    if (action === "INVESTIGATE" || action === "FIX_LINK" || action === "RECALCULATE") item.status = "IN_REVIEW";
    if (action === "JUSTIFY") item.status = "JUSTIFIED_EXCEPTION";
    if (action === "RESOLVE") item.status = "RESOLVED";
    if (action === "REOPEN") { item.status = "OPEN"; item.resolvedAt = undefined; item.resolvedBy = undefined; }
    if (notes.trim()) item.resolutionNotes = item.resolutionNotes ? `${item.resolutionNotes}\n${notes}` : notes;
    if (["JUSTIFY", "RESOLVE"].includes(action)) { item.resolvedAt = timestamp; item.resolvedBy = responsible; }
    item.updatedAt = timestamp;
    if (item.sourceTreasuryDivergenceId && ["JUSTIFY", "RESOLVE"].includes(action)) {
      const treasury = this.state.treasuryDivergences.find((value) => value.id === item.sourceTreasuryDivergenceId);
      if (treasury) { treasury.status = action === "JUSTIFY" ? "JUSTIFIED_EXCEPTION" : "RESOLVED"; treasury.resolutionNotes = notes; treasury.resolvedAt = timestamp; treasury.resolvedBy = responsible; }
    }
    this.audit("DIVERGENCE", id, action, notes || `Ação ${action} registrada na divergência de Receita.`, responsible);
    this.persist(); return structuredClone(item);
  }

  registerRevenueAdjustment(receiptId: string, amount: Cents, direction: "ENTRADA" | "SAIDA", details: { date: string; cashAccount: string; owner: string; notes: string }): TreasuryEntry {
    this.findIncoming(receiptId); this.assertMoney(amount);
    return this.createTreasuryEntry({ incomingReceiptId: receiptId, type: direction === "ENTRADA" ? "ADJUSTMENT_IN" : "ADJUSTMENT_OUT", direction, amount, date: details.date, competence: monthOf(details.date), cashAccount: details.cashAccount, status: "CONFIRMADO", owner: details.owner, reference: `AJUSTE-RECEITA:${receiptId}`, notes: details.notes });
  }

  createTreasuryEntry(input: TreasuryEntryInput): TreasuryEntry { this.assertMoney(input.amount); const item: TreasuryEntry = { id: this.nextId("mov"), ...input, createdAt: this.timestamp() }; this.state.treasuryEntries.push(item); this.audit("TREASURY", item.id, "CRIACAO", `Movimento ${item.type} criado.`); this.persist(); return structuredClone(item); }
  updateTreasuryEntry(id: string, input: TreasuryEntryInput): TreasuryEntry { this.assertMoney(input.amount); const item = this.state.treasuryEntries.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Movimento não encontrado."); Object.assign(item, input); this.audit("TREASURY", id, "EDICAO", `Movimento ${item.type} atualizado.`); this.persist(); return structuredClone(item); }
  cancelTreasuryEntry(id: string): TreasuryEntry { const item = this.state.treasuryEntries.find((value) => value.id === id); if (!item) throw new RepositoryValidationError("Movimento não encontrado."); if (item.status === "CONFIRMADO") throw new RepositoryValidationError("Movimentos confirmados devem ser estornados."); item.status = "CANCELADO"; this.audit("TREASURY", id, "CANCELAMENTO", "Movimento cancelado e preservado."); this.persist(); return structuredClone(item); }
  reverseTreasuryEntry(id: string, details: { date: string; owner: string; notes: string }): TreasuryEntry { const original = this.state.treasuryEntries.find((item) => item.id === id); if (!original || original.status !== "CONFIRMADO") throw new RepositoryValidationError("Somente movimentos confirmados podem ser estornados."); original.status = "ESTORNADO"; const reversal: TreasuryEntry = { id: this.nextId("mov"), investorId: original.investorId, contributionId: original.contributionId, capitalRemunerationEventId: original.capitalRemunerationEventId, fundingContractId: original.fundingContractId, incomingReceiptId: original.incomingReceiptId, bankMovementId: original.bankMovementId, type: original.direction === "ENTRADA" ? "REVERSAL_OUT" : original.direction === "SAIDA" ? "REVERSAL_IN" : "CAPITAL_DEALLOCATED", direction: original.direction === "ENTRADA" ? "SAIDA" : original.direction === "SAIDA" ? "ENTRADA" : "TRANSFERENCIA_INTERNA", amount: original.amount, date: details.date, competence: monthOf(details.date), cashAccount: original.cashAccount, status: "CONFIRMADO", owner: details.owner, reference: `ESTORNO:${original.reference}`, notes: details.notes, createdAt: this.timestamp() }; this.state.treasuryEntries.push(reversal); this.audit("TREASURY", id, "ESTORNO", `Original preservado; contrapartida ${reversal.id} criada.`, details.owner); this.persist(); return structuredClone(reversal); }
  reconcile(input: ReconciliationInput): Reconciliation { this.assertMoney(input.informedBalance); const calculated = cents(computeCashBalance(this.state.treasuryEntries, input.cashAccount)); const difference = cents(input.informedBalance) - calculated; const item: Reconciliation = { id: this.nextId("rec"), ...input, calculatedBalance: centsString(calculated), difference: centsString(difference), status: difference === 0n ? "CONCILIADO" : "DIVERGENTE" }; this.state.reconciliations.push(item); this.audit("RECONCILIATION", item.id, "CONCILIACAO", `Conciliação ${item.status}.`); this.persist(); return structuredClone(item); }
  registerReconciliationAdjustment(id: string): TreasuryEntry { const rec = this.state.reconciliations.find((item) => item.id === id); if (!rec || cents(rec.difference) === 0n) throw new RepositoryValidationError("Conciliação sem diferença."); const difference = cents(rec.difference); const entry = this.createTreasuryEntry({ type: difference > 0n ? "ADJUSTMENT_IN" : "ADJUSTMENT_OUT", direction: difference > 0n ? "ENTRADA" : "SAIDA", amount: centsString(absolute(difference)), date: rec.date, competence: monthOf(rec.date), cashAccount: rec.cashAccount, status: "CONFIRMADO", owner: rec.owner, reference: `AJUSTE:${rec.id}`, notes: rec.notes }); rec.calculatedBalance = rec.informedBalance; rec.difference = "0"; rec.status = "CONCILIADO"; this.audit("RECONCILIATION", id, "AJUSTE", "Ajuste demonstrativo registrado."); this.persist(); return entry; }
}

export function createBrowserFundingRepository(): FundingRepository { return new FundingRepository(window.localStorage); }
