import { buildRevenueRecords, calculateApuratedAmount } from "@/lib/revenue";
import type { Cents, FundingContract, FundingState, TreasuryIncomingReceipt } from "@/types/funding";

export const DEMO_REPORT_AS_OF = "2026-08-07";

export type ReportGranularity = "month" | "year";
export type ReportRangePreset = "all" | "last6" | "last12" | "last24" | "custom";
export interface ReportPeriodOptions {
  granularity?: ReportGranularity;
  preset?: ReportRangePreset;
  from?: string;
  to?: string;
  asOf?: string;
}

export interface HarvestReportRow {
  period: string; contractCount: number; newContractCount: number; averageTermMonths: number;
  weightedInterestRateBps: number; principal: Cents; released: Cents; iof: Cents;
  projectedTotal: Cents; projectedHarvest: Cents; nominalReceipt: Cents; realReceipt: Cents;
  refinancingDecapitalization: Cents; due: Cents; overdue: Cents; netLoss: Cents;
  delinquencyBps: number; sourceContractIds: string[]; sourceReceiptIds: string[];
}

export interface RevenueReportRow {
  competence: string; expectedPmt: Cents; paid: Cents; principal: Cents; interest: Cents;
  iof: Cents; penalty: Cents; discount: Cents; loss: Cents; apurated: Cents;
  nominalReceived: Cents; realReceived: Cents; due: Cents; overdue: Cents;
  installmentCount: number; validatedCount: number; divergentCount: number; sourceReceiptIds: string[];
}

export interface FundingReportRow {
  id: string; label: string; kind: "INVESTOR" | "REMO_OWN_CAPITAL" | "OTHER_SOURCE";
  investorId?: string; sourceIds: string[]; contributionIds: string[]; contractIds: string[];
  originalCapital: Cents; availableCapital: Cents; allocatedCapital: Cents; contractCount: number;
  financedPrincipal: Cents; released: Cents; projected: Cents; principalRecovered: Cents;
  interestReceived: Cents; capitalRemuneration: Cents; returnedCapital: Cents; reinvested: Cents;
  balance: Cents; overdue: Cents; loss: Cents; returnBps: number; delinquencyBps: number;
}

export interface FundingEvolutionPoint { competence: string; cumulativeCapital: Cents; cumulativeAllocated: Cents; }

export type DemonstrativeRating = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "HH";
export const PDD_RATING_DESCRIPTIONS: Record<DemonstrativeRating, string> = {
  A: "Menor que 15 dias", B: "Entre 15 e 30 dias", C: "Entre 31 e 60 dias",
  D: "Entre 61 e 90 dias", E: "Entre 91 e 120 dias", F: "Entre 121 e 150 dias",
  G: "Entre 151 e 180 dias", H: "Acima de 180 dias", HH: "Prejuízo",
};

export interface PddReportRow {
  rating: DemonstrativeRating; description: string; weightedInterestRateBps: number;
  clientCount: number; clientShareBps: number; contractCount: number; contractShareBps: number;
  principal: Cents; principalShareBps: number; received: Cents; receivedShareBps: number;
  pending: Cents; pendingShareBps: number; pddAmount?: Cents; pddShareBps?: number;
  pddRuleStatus: "RULE_TO_CONFIRM"; contractIds: string[];
}

export interface PddReportTotals {
  clientCount: number; contractCount: number; weightedInterestRateBps: number;
  principal: Cents; received: Cents; pending: Cents;
  pddAmount?: Cents;
}
export interface PddRatingHistoryPoint { competence: string; rating: DemonstrativeRating; principal: Cents; }
export interface PddReport { rows: PddReportRow[]; totals: PddReportTotals; history: PddRatingHistoryPoint[]; }

export interface InvestorCashFlowRow {
  competence: string; openingBalance: Cents; contributions: Cents; allocations: Cents;
  principalReceived: Cents; interestReceived: Cents; remuneration: Cents; roc?: Cents;
  rocRuleStatus: "RULE_TO_CONFIRM"; reinvestments: Cents; returns: Cents; adjustments: Cents;
  closingBalance: Cents; allocatedBalance: Cents; utilizationBps: number;
  detail: InvestorCashFlowMonthDetail;
}

export interface InvestorCashFlowMonthEvent { id: string; label: string; amount: Cents; }
export interface InvestorCashFlowMonthDetail {
  fundedContracts: InvestorCashFlowMonthEvent[]; principalReceipts: InvestorCashFlowMonthEvent[];
  interestReceipts: InvestorCashFlowMonthEvent[]; remunerations: InvestorCashFlowMonthEvent[];
  reinvestments: InvestorCashFlowMonthEvent[]; returns: InvestorCashFlowMonthEvent[];
  adjustments: InvestorCashFlowMonthEvent[];
}

export interface InvestorCashFlowReport {
  investorId: string; investorCode: string; initialDate?: string; originalContribution: Cents;
  additionalContributions: Cents; currentCapital: Cents; availableCapital: Cents;
  allocatedCapital: Cents; principalReceived: Cents; interestReceived: Cents;
  paidRemuneration: Cents; currentUtilizationBps: number;
  rows: InvestorCashFlowRow[]; contributionIds: string[]; contractIds: string[];
  remunerationIds: string[]; treasuryEntryIds: string[];
}

function money(value: Cents | undefined): bigint {
  if (!value || !/^-?\d+$/.test(value)) return 0n;
  return BigInt(value);
}

function asCents(value: bigint): Cents { return value.toString(); }
function positive(value: bigint): bigint { return value > 0n ? value : 0n; }
function sum(values: Array<Cents | undefined>): bigint { return values.reduce<bigint>((total, value) => total + money(value), 0n); }
function basisPointDistribution(weights: bigint[]): number[] {
  const total = weights.reduce((value, weight) => value + weight, 0n); if (total <= 0n) return weights.map(() => 0);
  const values = weights.map((weight) => weight * 10_000n / total); let remainder = 10_000n - values.reduce((value, part) => value + part, 0n);
  const order = weights.map((weight, index) => ({ index, remainder: weight * 10_000n % total })).sort((left, right) => left.remainder === right.remainder ? left.index - right.index : left.remainder > right.remainder ? -1 : 1);
  for (let index = 0; remainder > 0n; index += 1, remainder -= 1n) values[order[index % order.length].index] += 1n;
  return values.map((value) => Number(value));
}

export function ratioBps(numerator: Cents | bigint, denominator: Cents | bigint): number {
  const top = typeof numerator === "bigint" ? numerator : money(numerator);
  const bottom = typeof denominator === "bigint" ? denominator : money(denominator);
  if (bottom <= 0n) return 0;
  return Number((top * 10_000n + bottom / 2n) / bottom);
}

export function weightedAverageBps(items: { weight: Cents; rateBps: number }[]): number {
  const totalWeight = items.reduce((total, item) => total + money(item.weight), 0n);
  if (totalWeight <= 0n) return 0;
  const numerator = items.reduce((total, item) => total + money(item.weight) * BigInt(item.rateBps), 0n);
  return Number((numerator + totalWeight / 2n) / totalWeight);
}

function monthIndex(value: string): number {
  const [year, month] = value.slice(0, 7).split("-").map((item) => Number.parseInt(item, 10));
  return year * 12 + month - 1;
}

function monthFromIndex(value: number): string {
  const year = Math.floor(value / 12); const month = value % 12 + 1;
  return `${year}-${String(month).padStart(2, "0")}`;
}

export function resolveReportRange(options: ReportPeriodOptions = {}): { from?: string; to?: string } {
  const preset = options.preset ?? "all"; const asOf = options.asOf ?? DEMO_REPORT_AS_OF;
  if (preset === "custom") return { from: options.from, to: options.to };
  if (preset === "last6" || preset === "last12" || preset === "last24") {
    const months = preset === "last6" ? 6 : preset === "last12" ? 12 : 24;
    return { from: `${monthFromIndex(monthIndex(asOf) - months + 1)}-01`, to: asOf };
  }
  return {};
}

function isInRange(date: string, range: { from?: string; to?: string }): boolean {
  return (!range.from || date >= range.from) && (!range.to || date <= range.to);
}

function periodKey(date: string, granularity: ReportGranularity): string {
  return granularity === "year" ? date.slice(0, 4) : date.slice(0, 7);
}

function confirmedReceiptAmount(state: FundingState, receiptId: string): bigint {
  return state.treasuryEntries.filter((item) => item.incomingReceiptId === receiptId && item.type === "PMT_RECEIVED" && item.status === "CONFIRMADO").reduce((total, item) => total + money(item.amount), 0n);
}

function receiptOutstanding(state: FundingState, receipt: TreasuryIncomingReceipt): bigint {
  return positive(money(receipt.expectedAmount) - confirmedReceiptAmount(state, receipt.id));
}

function projected(contract: FundingContract): Cents { return contract.projectedAmount ?? contract.financedAmount; }

function isNewClientContract(state: FundingState, contract: FundingContract): boolean {
  return !state.fundingContracts.some((item) => item.maskedClientName === contract.maskedClientName
    && (item.operationDate < contract.operationDate || (item.operationDate === contract.operationDate && item.id < contract.id)));
}

export function buildHarvestReport(state: FundingState, options: ReportPeriodOptions = {}): HarvestReportRow[] {
  const granularity = options.granularity ?? "month"; const range = resolveReportRange(options); const asOf = options.asOf ?? DEMO_REPORT_AS_OF;
  const contracts = state.fundingContracts.filter((item) => isInRange(item.operationDate, range));
  const buckets = new Map<string, FundingContract[]>();
  contracts.forEach((contract) => { const key = periodKey(contract.operationDate, granularity); buckets.set(key, [...(buckets.get(key) ?? []), contract]); });
  return [...buckets.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([period, rows]) => {
    const contractIds = new Set(rows.map((item) => item.id));
    const receipts = state.treasuryIncomingReceipts.filter((item) => item.fundingContractId && contractIds.has(item.fundingContractId));
    const principal = sum(rows.map((item) => item.principalAmount)); const released = sum(rows.map((item) => item.releasedAmount));
    const projectedTotal = sum(rows.map((item) => projected(item))); const projectedHarvest = sum(receipts.map((item) => item.expectedAmount));
    const nominalReceipt = sum(receipts.map((item) => item.paidAmountFromOperationalSource));
    const realReceipt = receipts.reduce((total, item) => total + confirmedReceiptAmount(state, item.id), 0n);
    const due = receipts.filter((item) => item.dueDate >= asOf).reduce((total, item) => total + receiptOutstanding(state, item), 0n);
    const overdue = receipts.filter((item) => item.dueDate < asOf).reduce((total, item) => total + receiptOutstanding(state, item), 0n);
    const weightedTerm = principal <= 0n ? 0 : Number(rows.reduce((total, item) => total + money(item.principalAmount) * BigInt(item.termMonths), 0n) / principal);
    return {
      period, contractCount: rows.length, newContractCount: rows.filter((item) => isNewClientContract(state, item)).length,
      averageTermMonths: weightedTerm, weightedInterestRateBps: weightedAverageBps(rows.map((item) => ({ weight: item.principalAmount, rateBps: item.interestRateBps }))),
      principal: asCents(principal), released: asCents(released), iof: asCents(sum(receipts.map((item) => item.iofAmount))),
      projectedTotal: asCents(projectedTotal), projectedHarvest: asCents(projectedHarvest), nominalReceipt: asCents(nominalReceipt), realReceipt: asCents(realReceipt),
      refinancingDecapitalization: asCents(rows.reduce((total, item) => total + positive(money(item.financedAmount) - money(item.principalAmount)), 0n)),
      due: asCents(due), overdue: asCents(overdue), netLoss: asCents(sum(receipts.map((item) => item.lossAmount))),
      delinquencyBps: ratioBps(overdue, due + overdue), sourceContractIds: rows.map((item) => item.id), sourceReceiptIds: receipts.map((item) => item.id),
    };
  });
}

export function aggregateHarvestRows(rows: HarvestReportRow[]) {
  const principal = sum(rows.map((item) => item.principal)); const released = sum(rows.map((item) => item.released));
  const due = sum(rows.map((item) => item.due)); const overdue = sum(rows.map((item) => item.overdue));
  return {
    contracts: rows.reduce((total, item) => total + item.contractCount, 0), newContracts: rows.reduce((total, item) => total + item.newContractCount, 0),
    principal: asCents(principal), released: asCents(released), realReceipt: asCents(sum(rows.map((item) => item.realReceipt))),
    due: asCents(due), overdue: asCents(overdue), netLoss: asCents(sum(rows.map((item) => item.netLoss))), delinquencyBps: ratioBps(overdue, due + overdue),
  };
}

export function buildRevenueReport(state: FundingState, options: ReportPeriodOptions = {}): RevenueReportRow[] {
  const range = resolveReportRange(options); const asOf = options.asOf ?? DEMO_REPORT_AS_OF;
  const records = buildRevenueRecords(state); const recordById = new Map(records.map((item) => [item.id, item]));
  const receipts = state.treasuryIncomingReceipts.filter((item) => isInRange(item.operationalWriteOffDate ?? item.dueDate, range));
  const buckets = new Map<string, TreasuryIncomingReceipt[]>();
  receipts.forEach((receipt) => { const key = (receipt.operationalWriteOffDate ?? receipt.dueDate).slice(0, 7); buckets.set(key, [...(buckets.get(key) ?? []), receipt]); });
  return [...buckets.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([competence, rows]) => {
    const real = rows.reduce((total, item) => total + confirmedReceiptAmount(state, item.id), 0n);
    const due = rows.filter((item) => item.dueDate >= asOf).reduce((total, item) => total + receiptOutstanding(state, item), 0n);
    const overdue = rows.filter((item) => item.dueDate < asOf).reduce((total, item) => total + receiptOutstanding(state, item), 0n);
    return {
      competence, expectedPmt: asCents(sum(rows.map((item) => item.expectedAmount))), paid: asCents(sum(rows.map((item) => item.paidAmountFromOperationalSource))),
      principal: asCents(sum(rows.map((item) => item.principalAmount))), interest: asCents(sum(rows.map((item) => item.interestAmount))),
      iof: asCents(sum(rows.map((item) => item.iofAmount))), penalty: asCents(sum(rows.map((item) => item.penaltyAmount))),
      discount: asCents(sum(rows.map((item) => item.discountAmount))), loss: asCents(sum(rows.map((item) => item.lossAmount))),
      apurated: asCents(sum(rows.map((item) => calculateApuratedAmount(item)))), nominalReceived: asCents(sum(rows.map((item) => item.paidAmountFromOperationalSource))),
      realReceived: asCents(real), due: asCents(due), overdue: asCents(overdue), installmentCount: rows.length,
      validatedCount: rows.filter((item) => recordById.get(item.id)?.revenueStatus === "VALIDATED").length,
      divergentCount: rows.filter((item) => ["COMPONENT_DIVERGENCE", "BANK_DIVERGENCE", "PARTIALLY_VALIDATED"].includes(recordById.get(item.id)?.revenueStatus ?? "")).length,
      sourceReceiptIds: rows.map((item) => item.id),
    };
  });
}

export function aggregateRevenueRows(rows: RevenueReportRow[]) {
  return {
    expected: asCents(sum(rows.map((item) => item.expectedPmt))), paid: asCents(sum(rows.map((item) => item.paid))),
    principal: asCents(sum(rows.map((item) => item.principal))), interest: asCents(sum(rows.map((item) => item.interest))),
    realReceived: asCents(sum(rows.map((item) => item.realReceived))), due: asCents(sum(rows.map((item) => item.due))),
    overdue: asCents(sum(rows.map((item) => item.overdue))), loss: asCents(sum(rows.map((item) => item.loss))),
    installments: rows.reduce((total, item) => total + item.installmentCount, 0), validated: rows.reduce((total, item) => total + item.validatedCount, 0),
    divergent: rows.reduce((total, item) => total + item.divergentCount, 0),
  };
}

function allocationShare(value: Cents, allocationAmount: Cents, releasedAmount: Cents): bigint {
  const released = money(releasedAmount); if (released <= 0n) return 0n;
  return money(value) * money(allocationAmount) / released;
}

export function buildFundingReport(state: FundingState, options: ReportPeriodOptions = {}): FundingReportRow[] {
  const range = resolveReportRange(options); const currentAllocations = state.contractFundingAllocations.filter((item) => !item.supersededAt && isInRange(item.allocationDate, range));
  const groups: Array<{ id: string; label: string; kind: FundingReportRow["kind"]; investorId?: string; sourceIds: string[]; contributionIds: string[] }> = [];
  state.investors.forEach((investor) => { const contributions = state.contributions.filter((item) => item.investorId === investor.id); const contributionIds = contributions.map((item) => item.id); const sourceIds = state.fundingSources.filter((item) => item.reference && contributionIds.includes(item.reference)).map((item) => item.id); groups.push({ id: investor.id, label: investor.name, kind: "INVESTOR", investorId: investor.id, sourceIds, contributionIds }); });
  state.fundingSources.filter((item) => item.type !== "INVESTOR_CONTRIBUTION").forEach((source) => groups.push({ id: source.id, label: source.name, kind: source.type === "REMO_OWN_CAPITAL" ? "REMO_OWN_CAPITAL" : "OTHER_SOURCE", sourceIds: [source.id], contributionIds: [] }));
  return groups.map((group) => {
    const contributions = state.contributions.filter((item) => group.contributionIds.includes(item.id) && isInRange(item.startDate, range));
    const allocations = currentAllocations.filter((item) => group.investorId
      ? item.investorId === group.investorId
      : Boolean(item.fundingSourceId && group.sourceIds.includes(item.fundingSourceId)));
    const contractIds = [...new Set(allocations.map((item) => item.fundingContractId))];
    let financedPrincipal = 0n; let released = 0n; let projectedValue = 0n; let overdue = 0n; let loss = 0n;
    allocations.forEach((allocation) => { const contract = state.fundingContracts.find((item) => item.id === allocation.fundingContractId); if (!contract) return; financedPrincipal += allocationShare(contract.principalAmount, allocation.amount, contract.releasedAmount); released += money(allocation.amount); projectedValue += allocationShare(projected(contract), allocation.amount, contract.releasedAmount); state.treasuryIncomingReceipts.filter((item) => item.fundingContractId === contract.id).forEach((receipt) => { if (receipt.dueDate < (options.asOf ?? DEMO_REPORT_AS_OF)) overdue += allocationShare(asCents(receiptOutstanding(state, receipt)), allocation.amount, contract.releasedAmount); loss += allocationShare(receipt.lossAmount, allocation.amount, contract.releasedAmount); }); });
    const allocationIds = new Set(allocations.map((item) => item.id));
    const shares = state.allocationReceiptShares.filter((item) => allocationIds.has(item.contractFundingAllocationId) && item.status !== "REVERSED");
    const remunerationEvents = state.capitalRemunerationEvents.filter((item) => group.investorId === item.investorId && isInRange(`${item.competence}-01`, range));
    const relatedTreasury = state.treasuryEntries.filter((item) => item.investorId === group.investorId || (item.contributionId && group.contributionIds.includes(item.contributionId)));
    const sourceCapital = sum(group.sourceIds.map((id) => state.fundingSources.find((item) => item.id === id)?.historicalAvailableAmount));
    const original = group.kind === "INVESTOR" ? sum(contributions.map((item) => item.originalAmount)) : sourceCapital;
    const available = group.kind === "INVESTOR" ? sum(contributions.map((item) => item.availableBalance)) : positive(sourceCapital - released);
    const principalRecovered = sum(shares.map((item) => item.principalShare)); const interestReceived = sum(shares.map((item) => item.interestShare));
    const returned = sum(relatedTreasury.filter((item) => item.type === "CAPITAL_RETURNED" && item.status === "CONFIRMADO").map((item) => item.amount));
    const reinvested = sum(relatedTreasury.filter((item) => ["CAPITAL_REINVESTED", "REMUNERATION_REINVESTED"].includes(item.type) && item.status === "CONFIRMADO").map((item) => item.amount));
    const remuneration = sum(remunerationEvents.map((item) => item.netAmount));
    return {
      id: group.id, label: group.label, kind: group.kind, investorId: group.investorId, sourceIds: group.sourceIds,
      contributionIds: group.contributionIds, contractIds, originalCapital: asCents(original), availableCapital: asCents(available), allocatedCapital: asCents(released), contractCount: contractIds.length,
      financedPrincipal: asCents(financedPrincipal), released: asCents(released), projected: asCents(projectedValue), principalRecovered: asCents(principalRecovered),
      interestReceived: asCents(interestReceived), capitalRemuneration: asCents(remuneration), returnedCapital: asCents(returned), reinvested: asCents(reinvested),
      balance: asCents(positive(available + principalRecovered + reinvested - returned)), overdue: asCents(overdue), loss: asCents(loss),
      returnBps: ratioBps(interestReceived + remuneration, original), delinquencyBps: ratioBps(overdue, released),
    };
  });
}

export function buildFundingEvolution(state: FundingState, options: ReportPeriodOptions = {}): FundingEvolutionPoint[] {
  const range = resolveReportRange(options);
  const contributions = state.contributions.filter((item) => isInRange(item.startDate, range));
  const allocations = state.contractFundingAllocations.filter((item) => !item.supersededAt && isInRange(item.allocationDate, range));
  const competences = [...new Set([...contributions.map((item) => item.startDate.slice(0, 7)), ...allocations.map((item) => item.allocationDate.slice(0, 7))])].sort();
  let capital = 0n; let allocated = 0n;
  return competences.map((competence) => {
    capital += sum(contributions.filter((item) => item.startDate.slice(0, 7) === competence).map((item) => item.originalAmount));
    allocated += sum(allocations.filter((item) => item.allocationDate.slice(0, 7) === competence).map((item) => item.amount));
    return { competence, cumulativeCapital: asCents(capital), cumulativeAllocated: asCents(allocated) };
  });
}

function daysBetween(later: string, earlier: string): number {
  const laterUtc = Date.parse(`${later.slice(0, 10)}T00:00:00Z`); const earlierUtc = Date.parse(`${earlier.slice(0, 10)}T00:00:00Z`);
  return Math.max(0, Math.floor((laterUtc - earlierUtc) / 86_400_000));
}

export function classifyPddRating(state: FundingState, contract: FundingContract, asOf = DEMO_REPORT_AS_OF): DemonstrativeRating {
  const receipts = state.treasuryIncomingReceipts.filter((item) => item.fundingContractId === contract.id);
  if (receipts.some((item) => money(item.lossAmount) > 0n)) return "HH";
  const maximumDelay = receipts.filter((item) => item.dueDate < asOf && receiptOutstanding(state, item) > 0n)
    .reduce((maximum, item) => Math.max(maximum, daysBetween(asOf, item.dueDate)), 0);
  if (maximumDelay < 15) return "A";
  if (maximumDelay <= 30) return "B";
  if (maximumDelay <= 60) return "C";
  if (maximumDelay <= 90) return "D";
  if (maximumDelay <= 120) return "E";
  if (maximumDelay <= 150) return "F";
  if (maximumDelay <= 180) return "G";
  return "H";
}

function contractExposure(state: FundingState, contract: FundingContract): bigint {
  const recovered = state.treasuryIncomingReceipts.filter((item) => item.fundingContractId === contract.id && item.status === "VALIDATED").reduce((total, item) => total + money(item.principalAmount), 0n);
  return positive(money(contract.principalAmount) - recovered);
}

export function buildPddReport(state: FundingState, options: ReportPeriodOptions = {}): PddReport {
  const range = resolveReportRange(options); const asOf = options.asOf ?? DEMO_REPORT_AS_OF;
  const contracts = state.fundingContracts.filter((item) => isInRange(item.operationDate, range));
  const totalClients = new Set(contracts.map((item) => item.maskedClientName)).size; const totalContracts = contracts.length;
  const totalPrincipal = sum(contracts.map((item) => item.principalAmount));
  const receivedFor = (contractId: string) => state.treasuryIncomingReceipts.filter((item) => item.fundingContractId === contractId)
    .reduce((total, item) => total + confirmedReceiptAmount(state, item.id), 0n);
  const totalReceived = contracts.reduce((total, item) => total + receivedFor(item.id), 0n);
  const totalPending = contracts.reduce((total, item) => total + contractExposure(state, item), 0n);
  const ratings: DemonstrativeRating[] = ["A", "B", "C", "D", "E", "F", "G", "H", "HH"];
  const clientRatings = new Map<string, DemonstrativeRating>(); contracts.forEach((contract) => { const rating = classifyPddRating(state, contract, asOf); const current = clientRatings.get(contract.maskedClientName); if (!current || ratings.indexOf(rating) > ratings.indexOf(current)) clientRatings.set(contract.maskedClientName, rating); });
  const rawRows = ratings.map((rating) => {
    const rated = contracts.filter((item) => classifyPddRating(state, item, asOf) === rating);
    const clients = new Set([...clientRatings.entries()].filter(([, value]) => value === rating).map(([client]) => client)); const principal = sum(rated.map((item) => item.principalAmount));
    const received = rated.reduce((total, item) => total + receivedFor(item.id), 0n); const pending = rated.reduce((total, item) => total + contractExposure(state, item), 0n);
    return { rating, rated, clients, principal, received, pending };
  });
  const clientShares = basisPointDistribution(rawRows.map((item) => BigInt(item.clients.size))); const contractShares = basisPointDistribution(rawRows.map((item) => BigInt(item.rated.length)));
  const principalShares = basisPointDistribution(rawRows.map((item) => item.principal)); const receivedShares = basisPointDistribution(rawRows.map((item) => item.received)); const pendingShares = basisPointDistribution(rawRows.map((item) => item.pending));
  const rows: PddReportRow[] = rawRows.map((item, index) => ({ rating: item.rating, description: PDD_RATING_DESCRIPTIONS[item.rating], weightedInterestRateBps: weightedAverageBps(item.rated.map((contract) => ({ weight: contract.principalAmount, rateBps: contract.interestRateBps }))), clientCount: item.clients.size, clientShareBps: clientShares[index], contractCount: item.rated.length, contractShareBps: contractShares[index], principal: asCents(item.principal), principalShareBps: principalShares[index], received: asCents(item.received), receivedShareBps: receivedShares[index], pending: asCents(item.pending), pendingShareBps: pendingShares[index], pddRuleStatus: "RULE_TO_CONFIRM", contractIds: item.rated.map((contract) => contract.id) }));
  return { rows, totals: { clientCount: totalClients, contractCount: totalContracts, weightedInterestRateBps: weightedAverageBps(contracts.map((item) => ({ weight: item.principalAmount, rateBps: item.interestRateBps }))), principal: asCents(totalPrincipal), received: asCents(totalReceived), pending: asCents(totalPending) }, history: [] };
}

function monthSequence(from: string, to: string): string[] {
  const first = monthIndex(from); const last = monthIndex(to); const values: string[] = [];
  for (let current = first; current <= last; current += 1) values.push(monthFromIndex(current));
  return values;
}

export interface InvestorCashFlowOptions extends ReportPeriodOptions { contributionId?: string; }

export function buildInvestorCashFlowReport(state: FundingState, investorId: string, options: InvestorCashFlowOptions = {}): InvestorCashFlowReport {
  const investor = state.investors.find((item) => item.id === investorId); if (!investor) throw new Error("Investidor demonstrativo não encontrado.");
  const contributions = state.contributions.filter((item) => item.investorId === investorId && (!options.contributionId || item.id === options.contributionId)).sort((left, right) => left.startDate.localeCompare(right.startDate)); const contributionIds = contributions.map((item) => item.id);
  const allocations = state.contractFundingAllocations.filter((item) => !item.supersededAt && item.investorId === investorId && (!options.contributionId || item.contributionId === options.contributionId)); const allocationIds = new Set(allocations.map((item) => item.id));
  const shares = state.allocationReceiptShares.filter((item) => allocationIds.has(item.contractFundingAllocationId) && item.status !== "REVERSED");
  const remunerations = state.capitalRemunerationEvents.filter((item) => item.investorId === investorId && (!options.contributionId || item.contributionId === options.contributionId));
  const treasury = state.treasuryEntries.filter((item) => (item.investorId === investorId || (item.contributionId && contributionIds.includes(item.contributionId))) && (!options.contributionId || item.contributionId === options.contributionId));
  const ledger = state.fundingLedgerEntries.filter((item) => item.contributionId && contributionIds.includes(item.contributionId));
  const dates = [...contributions.map((item) => item.startDate), ...allocations.map((item) => item.allocationDate), ...remunerations.map((item) => `${item.competence}-01`), ...treasury.map((item) => item.date), ...ledger.map((item) => item.date)];
  const asOf = options.asOf ?? DEMO_REPORT_AS_OF; const range = resolveReportRange(options);
  const earliestEvent = dates.sort()[0]?.slice(0, 7) ?? asOf.slice(0, 7); const first = range.from && range.from.slice(0, 7) < earliestEvent ? range.from.slice(0, 7) : earliestEvent;
  const last = range.to?.slice(0, 7) ?? asOf.slice(0, 7); let balance = 0n; let allocatedBalance = 0n;
  const allRows = monthSequence(first, last).map((competence): InvestorCashFlowRow => {
    const opening = balance; const contributionAmount = sum(contributions.filter((item) => item.startDate.slice(0, 7) === competence).map((item) => item.originalAmount));
    const monthAllocations = allocations.filter((item) => item.allocationDate.slice(0, 7) === competence); const allocationAmount = sum(monthAllocations.map((item) => item.amount));
    const monthShares = shares.filter((share) => { const receipt = state.treasuryIncomingReceipts.find((item) => item.id === share.incomingReceiptId); return (receipt?.operationalWriteOffDate ?? receipt?.dueDate)?.slice(0, 7) === competence; });
    const principal = sum(monthShares.map((item) => item.principalShare)); const interest = sum(monthShares.map((item) => item.interestShare));
    const monthRemunerations = remunerations.filter((item) => item.competence === competence); const paid = sum(monthRemunerations.filter((item) => item.status === "PAGA").map((item) => item.netAmount));
    const reinvestmentEvents = monthRemunerations.filter((item) => item.status === "REINVESTIDA"); const reinvestments = sum(reinvestmentEvents.map((item) => item.netAmount));
    const returnEvents = treasury.filter((item) => item.type === "CAPITAL_RETURNED" && item.status === "CONFIRMADO" && item.competence === competence); const returns = sum(returnEvents.map((item) => item.amount));
    const ledgerAdjustments = ledger.filter((item) => item.date.slice(0, 7) === competence && ["REINTEGRATION", "REVERSAL"].includes(item.type));
    const treasuryAdjustments = treasury.filter((item) => item.competence === competence && item.status === "CONFIRMADO" && ["CAPITAL_DEALLOCATED", "REVERSAL_IN", "ADJUSTMENT_IN", "REVERSAL_OUT", "ADJUSTMENT_OUT"].includes(item.type));
    const adjustments = sum(ledgerAdjustments.map((item) => item.amount)) + treasuryAdjustments.reduce((total, item) => total + (["REVERSAL_OUT", "ADJUSTMENT_OUT"].includes(item.type) ? -money(item.amount) : money(item.amount)), 0n);
    balance = opening + contributionAmount + principal + adjustments + reinvestments - allocationAmount - returns;
    allocatedBalance = positive(allocatedBalance + allocationAmount - principal - adjustments);
    const utilizationBps = ratioBps(allocatedBalance, allocatedBalance + positive(balance));
    const detail: InvestorCashFlowMonthDetail = {
      fundedContracts: monthAllocations.map((item) => ({ id: item.id, label: state.fundingContracts.find((value) => value.id === item.fundingContractId)?.contractCode ?? item.fundingContractId, amount: item.amount })),
      principalReceipts: monthShares.map((item) => ({ id: item.id, label: state.treasuryIncomingReceipts.find((value) => value.id === item.incomingReceiptId)?.contractCode ?? item.incomingReceiptId, amount: item.principalShare })),
      interestReceipts: monthShares.map((item) => ({ id: item.id, label: state.treasuryIncomingReceipts.find((value) => value.id === item.incomingReceiptId)?.contractCode ?? item.incomingReceiptId, amount: item.interestShare })),
      remunerations: monthRemunerations.filter((item) => item.status === "PAGA").map((item) => ({ id: item.id, label: `Remuneração ${item.competence}`, amount: item.netAmount })),
      reinvestments: reinvestmentEvents.map((item) => ({ id: item.id, label: `Reinvestimento ${item.competence}`, amount: item.netAmount })),
      returns: returnEvents.map((item) => ({ id: item.id, label: item.reference, amount: item.amount })),
      adjustments: [...ledgerAdjustments.map((item) => ({ id: item.id, label: item.reference, amount: item.amount })), ...treasuryAdjustments.map((item) => ({ id: item.id, label: item.reference, amount: ["REVERSAL_OUT", "ADJUSTMENT_OUT"].includes(item.type) ? asCents(-money(item.amount)) : item.amount }))],
    };
    return { competence, openingBalance: asCents(opening), contributions: asCents(contributionAmount), allocations: asCents(allocationAmount), principalReceived: asCents(principal), interestReceived: asCents(interest), remuneration: asCents(paid), rocRuleStatus: "RULE_TO_CONFIRM", reinvestments: asCents(reinvestments), returns: asCents(returns), adjustments: asCents(adjustments), closingBalance: asCents(balance), allocatedBalance: asCents(allocatedBalance), utilizationBps, detail };
  });
  const rows = allRows.filter((item) => (!range.from || `${item.competence}-01` >= range.from.slice(0, 7) + "-01") && (!range.to || `${item.competence}-01` <= range.to.slice(0, 7) + "-01"));
  const original = contributions[0] ? money(contributions[0].originalAmount) : 0n; const additional = sum(contributions.slice(1).map((item) => item.originalAmount));
  const principalReceived = sum(rows.map((item) => item.principalReceived)); const interestReceived = sum(rows.map((item) => item.interestReceived)); const paidRemuneration = sum(rows.map((item) => item.remuneration));
  const finalRow = rows.at(-1); const available = money(finalRow?.closingBalance); const allocated = money(finalRow?.allocatedBalance); const currentCapital = positive(available) + allocated;
  return { investorId, investorCode: investor.code, initialDate: contributions[0]?.startDate, originalContribution: asCents(original), additionalContributions: asCents(additional), currentCapital: asCents(currentCapital), availableCapital: asCents(available), allocatedCapital: asCents(allocated), principalReceived: asCents(principalReceived), interestReceived: asCents(interestReceived), paidRemuneration: asCents(paidRemuneration), currentUtilizationBps: ratioBps(allocated, currentCapital), rows, contributionIds, contractIds: [...new Set(allocations.map((item) => item.fundingContractId))], remunerationIds: remunerations.map((item) => item.id), treasuryEntryIds: treasury.map((item) => item.id) };
}
