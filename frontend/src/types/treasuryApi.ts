export type TreasuryMovementType = "CONTRIBUTION" | "SALE" | "REVENUE" | "CAPITAL_REMUNERATION";
export type TreasuryDirection = "INFLOW" | "OUTFLOW";
export type TreasuryValidationStatus = "PENDING" | "VALIDATED" | "DIVERGENT";
export type TreasuryBankCode = "INTER" | "BTG" | "PICPAY" | "NUBANK" | "C6" | "CASH";

export interface TreasuryMovement {
  id: string;
  movement_type: TreasuryMovementType;
  direction: TreasuryDirection;
  movement_date: string | null;
  reference: string;
  description: string;
  contract_code: string | null;
  client_name: string | null;
  installment_code: string | null;
  data_quality_status: string | null;
  funding_status: string | null;
  investor_id: string | null;
  investor_name: string | null;
  inflow: string | null;
  outflow: string | null;
  amount: string | null;
  sale_id?: string | null;
  released_amount?: string | null;
  continuity_type?: "REFINANCING" | "RENEGOTIATION" | "ROLLOVER" | null;
  continuity_role?: "PREDECESSOR" | "SUCCESSOR" | null;
  origin: string;
  source_record_id: string;
  source_batch_id?: number | null;
  detail_path: string;
  status: string;
  financial_operator: string | null;
  financial_account: string | null;
  validation_status: TreasuryValidationStatus;
  validation_id: string | null;
  observed_amount: string | null;
  observed_date: string | null;
  difference_amount: string | null;
  bank_reference: string | null;
  bank_code?: TreasuryBankCode | null;
  validated_at: string | null;
  validated_by: string | null;
  validation_justification: string | null;
}

export interface TreasurySummary {
  period_from: string | null;
  period_to: string | null;
  total_inflows: string;
  total_outflows: string;
  known_net_flow: string;
  contributions: string;
  revenues: string;
  sales: string;
  contribution_count: number;
  revenue_count: number;
  sale_count: number;
  undated_movement_count: number;
  unknown_amount_count: number;
  pending_validation_count: number;
  validated_count: number;
  divergent_count: number;
  net_difference_amount: string;
}

export interface TreasuryFilters {
  page?: number;
  page_size?: number;
  period_from?: string;
  period_to?: string;
  movement_type?: Exclude<TreasuryMovementType, "CAPITAL_REMUNERATION"> | "";
  search?: string;
  installment?: string;
  investor_id?: string;
  validation_status?: TreasuryValidationStatus | "";
  eligible_for_validation?: boolean;
}

export interface TreasuryValidation {
  id: string;
  movement_key: string;
  version: number;
  is_current: boolean;
  supersedes_validation_id: string | null;
  movement_type: Exclude<TreasuryMovementType, "CAPITAL_REMUNERATION">;
  direction: TreasuryDirection;
  system_amount_snapshot: string;
  system_date_snapshot: string | null;
  observed_amount: string;
  observed_date: string;
  difference_amount: string;
  status: Exclude<TreasuryValidationStatus, "PENDING">;
  bank_reference: string | null;
  bank_code: TreasuryBankCode | null;
  justification: string | null;
  validated_at: string;
  validated_by: string | null;
  created_at: string;
}

export interface TreasuryValidationInput {
  observed_amount: string;
  observed_date: string;
  bank_reference: string | null;
  bank_code?: TreasuryBankCode | null;
  justification: string | null;
}

export interface TreasuryValidationState {
  movement_key: string;
  status: TreasuryValidationStatus;
  current: TreasuryValidation | null;
}

export interface TreasuryValidationHistory {
  movement_key: string;
  items: TreasuryValidation[];
}

export interface TreasuryMovementsPage {
  items: TreasuryMovement[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    pages: number;
  };
}
