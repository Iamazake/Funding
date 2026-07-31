export type Money = string;

export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

export type InvestorStatus = "active" | "pending" | "inactive";
export type InvestorType = "individual" | "company" | "fund";
export type ContributionStatus = "available" | "partially_allocated" | "allocated" | "closed";
export type ContractStatus = "available" | "partial" | "funded";
export type TreasuryMovementType =
  | "contribution"
  | "allocation"
  | "remuneration"
  | "refund"
  | "reinvestment"
  | "pjr";

export interface DashboardMetric {
  id: string;
  label: string;
  value: Money;
  variationPercent: string;
  direction: "up" | "down" | "stable";
}

export interface ChartPoint {
  label: string;
  value: number;
  secondaryValue?: number;
}

export interface DashboardActivity {
  id: string;
  title: string;
  description: string;
  occurredAt: string;
  tone: StatusTone;
}

export interface UpcomingPayment {
  id: string;
  investorName: string;
  dueDate: string;
  amount: Money;
  kind: "remuneration" | "refund" | "pjr";
}

export interface FundingDashboardData {
  metrics: DashboardMetric[];
  fundingEvolution: ChartPoint[];
  capitalPosition: ChartPoint[];
  investorDistribution: ChartPoint[];
  upcomingPayments: UpcomingPayment[];
  recentActivities: DashboardActivity[];
}

export interface Investor {
  id: string;
  name: string;
  type: InvestorType;
  status: InvestorStatus;
  maskedDocument: string;
  email: string;
  joinedAt: string;
  contributedCapital: Money;
  availableBalance: Money;
  allocatedBalance: Money;
  accumulatedReturn: Money;
  nextPaymentDate: string | null;
  nextPaymentAmount: Money;
}

export interface Contribution {
  id: string;
  code: string;
  investorId: string;
  investorName: string;
  status: ContributionStatus;
  originalAmount: Money;
  availableAmount: Money;
  allocatedAmount: Money;
  monthlyRate: string;
  startDate: string;
  endDate: string;
}

export interface Allocation {
  id: string;
  investorId: string;
  investorName: string;
  contributionId: string;
  contractId: string;
  contractCode: string;
  amount: Money;
  allocatedAt: string;
  status: "active" | "completed";
}

export interface InvestorRemuneration {
  id: string;
  investorId: string;
  reference: string;
  amount: Money;
  dueDate: string;
  status: "scheduled" | "paid";
}

export interface InvestorDetail extends Investor {
  contributions: Contribution[];
  allocations: Allocation[];
  remunerations: InvestorRemuneration[];
  movements: TreasuryMovement[];
  evolution: ChartPoint[];
}

export interface OperationalContract {
  id: string;
  code: string;
  maskedClientName: string;
  releasedAmount: Money;
  principalAmount: Money;
  installmentAmount: Money;
  termMonths: number;
  monthlyRate: string;
  status: ContractStatus;
  operationDate: string;
  requiredFunding: Money;
  allocatedFunding: Money;
  fundedPercent: string;
}

export interface AllocationDraftItem {
  contributionId: string;
  amount: Money;
}

export interface AllocationSimulation {
  contractId: string;
  items: AllocationDraftItem[];
}

export interface AllocationSimulationResult {
  success: boolean;
  message: string;
  allocatedAmount: Money;
  remainingAmount: Money;
}

export interface TreasuryMovement {
  id: string;
  type: TreasuryMovementType;
  investorId: string;
  investorName: string;
  date: string;
  amount: Money;
  direction: "in" | "out";
  description: string;
  status: "scheduled" | "completed";
}

export interface TreasurySummary {
  generalBalance: Money;
  totalInflows: Money;
  totalOutflows: Money;
  totalRemuneration: Money;
  totalRefunds: Money;
  totalReinvestments: Money;
  totalPjr: Money;
  movements: TreasuryMovement[];
}

export interface ReportSnapshot {
  generatedAt: string;
  fundingByInvestor: ChartPoint[];
  returnByInvestor: ChartPoint[];
  capitalPosition: ChartPoint[];
  remunerationForecast: ChartPoint[];
  treasuryByType: ChartPoint[];
  contractDistribution: ChartPoint[];
}

export interface FundingDashboardDataProvider {
  getDashboard(): Promise<FundingDashboardData>;
}

export interface InvestorsDataProvider {
  listInvestors(): Promise<Investor[]>;
  getInvestor(id: string): Promise<InvestorDetail | null>;
}

export interface ContributionsDataProvider {
  listContributions(): Promise<Contribution[]>;
  getContribution(id: string): Promise<Contribution | null>;
}

export interface AllocationsDataProvider {
  listAllocations(): Promise<Allocation[]>;
  simulateAllocation(input: AllocationSimulation): Promise<AllocationSimulationResult>;
}

export interface TreasuryDataProvider {
  getTreasury(): Promise<TreasurySummary>;
  getReports(): Promise<ReportSnapshot>;
}

export interface OperationalContractsDataProvider {
  listContracts(): Promise<OperationalContract[]>;
  getContract(id: string): Promise<OperationalContract | null>;
}
