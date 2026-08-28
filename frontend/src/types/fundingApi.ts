export type InvestorStatus = "ACTIVE" | "INACTIVE";
export type ContributionStatus = "ACTIVE" | "INACTIVE" | "CLOSED";

export interface FundingInvestor {
  id: string;
  code: string;
  name: string;
  tax_id_masked: string | null;
  phone: string | null;
  status: InvestorStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FundingContribution {
  id: string;
  code: string;
  investor_id: string;
  contribution_date: string;
  end_date?: string | null;
  original_amount: string;
  monthly_rate: string;
  status: ContributionStatus;
  notes: string | null;
  original_amount_editable: boolean;
  created_at: string;
  updated_at: string;
}

export interface FundingInvestorInput {
  name: string;
  tax_id?: string | null;
  phone: string | null;
  status: InvestorStatus;
  notes: string | null;
}

export interface FundingContributionInput {
  investor_id: string;
  contribution_date: string;
  end_date?: string | null;
  original_amount: string;
  monthly_rate: string;
  status: ContributionStatus;
  notes: string | null;
}

export interface ContributionAnalysisSummary {
  contribution_id: string;
  contribution_code: string;
  investor_id: string;
  investor_name: string;
  original_amount: string;
  available_balance: string;
  allocated_capital: string;
  returned_principal: string;
  exposed_capital: string;
  utilization_percentage: string;
  monthly_rate: string;
  contribution_date: string;
  status: ContributionStatus;
}

export interface ContributionOperationAnalysis {
  allocation_id: string;
  sale_id: string;
  sale_kind: "CONTRACT" | "ORPHAN_LOAN";
  contract_code: string | null;
  loan_id: number | null;
  client_name: string | null;
  operation_date: string;
  operation_amount: string | null;
  allocated_amount: string;
  operation_percentage: string | null;
  returned_principal: string;
  exposed_capital: string;
  allocation_status: "ACTIVE" | "REVERSED";
  funding_status: SaleFundingStatus;
}

export interface ContributionMovementAnalysis {
  id: number;
  effective_date: string;
  entry_type: string;
  origin_type: string;
  contribution_id: string | null;
  allocation_id: string | null;
  revenue_distribution_item_id: string | null;
  reversal_of_entry_id: number | null;
  inflow: string;
  outflow: string;
  running_balance: string;
  actor: string;
  notes: string | null;
  created_at: string;
}

export interface ContributionReturnAnalysis {
  distribution_id: string;
  distribution_item_id: string;
  revenue_id: string | number;
  sale_id: string;
  allocation_id: string;
  effective_date: string;
  status: "DISTRIBUTED" | "REVERSED";
  principal_amount: string;
  interest_amount: string;
  discount_amount: string;
}

export interface ContributionAnalysis {
  source_id: string;
  contribution: FundingContribution;
  investor: FundingInvestor;
  summary: ContributionAnalysisSummary;
  operations: ContributionOperationAnalysis[];
  movements: ContributionMovementAnalysis[];
  return_totals: {
    principal_amount: string;
    interest_amount: string;
    discount_amount: string;
  };
  returns: ContributionReturnAnalysis[];
}

export type FundingSourceType = "INVESTOR_CONTRIBUTION" | "REMO_CAPITAL";
export type SaleFundingStatus = "NOT_INFORMED" | "INCOMPLETE" | "COMPLETE" | "OVERFUNDED" | "BASE_AMOUNT_UNAVAILABLE";

export interface FundingSource {
  id: string;
  source_type: FundingSourceType;
  contribution_id: string | null;
  status: "ACTIVE" | "INACTIVE";
  investor_id: string | null;
  investor_name: string | null;
  contribution_code: string | null;
  contribution_date: string | null;
  original_amount: string | null;
  monthly_rate: string | null;
  current_balance: string;
  created_at: string;
  updated_at: string;
}

export interface FundingAllocation {
  id: string;
  sale_id: string;
  source_id: string;
  source_type: FundingSourceType;
  contribution_id: string | null;
  contribution_code: string | null;
  investor_id: string | null;
  investor_name: string | null;
  amount: string;
  percentage: string | null;
  effective_date: string;
  status: "ACTIVE" | "REVERSED";
  actor: string;
  notes: string | null;
  created_at: string;
  reversed_at: string | null;
  inherited_from_predecessor?: boolean;
  origin_sale_id?: string | null;
}

export interface SaleFundingComposition {
  sale_id: string;
  operation_date: string;
  base_field: "released_amount";
  operation_amount: string | null;
  identified_amount: string;
  difference: string | null;
  funding_status: SaleFundingStatus;
  source_count: number;
  allocations: FundingAllocation[];
  has_new_disbursement?: boolean;
  funding_origin_sale_id?: string | null;
}

export interface SourceBalance {
  source_id: string;
  as_of: string | null;
  balance: string;
}

export interface LedgerEntry {
  id: number;
  source_id: string;
  entry_type: string;
  amount: string;
  direction: -1 | 1;
  signed_amount: string;
  effective_date: string;
  origin_type: string;
  allocation_id: string | null;
  revenue_distribution_item_id: string | null;
  reversal_of_entry_id: number | null;
  actor: string;
  notes: string | null;
  created_at: string;
}

export type RevenueDistributionStatus = "PENDING_FUNDING" | "READY" | "DISTRIBUTED" | "DIVERGENT" | "REVERSED";

export interface RevenueDistributionItem {
  id: string;
  source_id: string;
  source_type: FundingSourceType;
  allocation_id: string;
  contribution_id: string | null;
  contribution_code: string | null;
  investor_id: string | null;
  investor_name: string | null;
  participation_rate: string;
  percentage: string;
  allocation_amount: string;
  principal_amount: string;
  interest_amount: string;
  discount_amount: string;
  total_amount: string;
}

export interface RevenueDistribution {
  id: string | null;
  revenue_id: string | number;
  sale_id: string | null;
  version: number | null;
  status: RevenueDistributionStatus;
  funding_status: SaleFundingStatus | null;
  reason: string | null;
  effective_date: string | null;
  base_amount: string | null;
  principal_amount: string;
  interest_amount: string;
  discount_amount: string;
  identified_amount: string;
  distributed_principal: string;
  distributed_interest: string;
  distributed_discount: string;
  unidentified_principal: string;
  unidentified_interest: string;
  unidentified_discount: string;
  distributed_total: string;
  unidentified_total: string;
  primary_source_name: string | null;
  source_count: number;
  items: RevenueDistributionItem[];
  created_at: string | null;
  reversed_at: string | null;
}
