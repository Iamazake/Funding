export type DataQuality = "VALID" | "WARNING" | "DIVERGENT" | "INVALID";

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface QualityMessage {
  type: string;
  severity: "WARNING" | "DIVERGENT";
  message: string;
}

export interface SaleItem {
  id: string;
  contract_code: string | null;
  client_name: string | null;
  source_client_code: string | null;
  operation_date: string | null;
  release_date: string | null;
  first_due_date: string | null;
  term: number | null;
  principal: string | null;
  iof: string | null;
  financed_amount: string | null;
  installment_amount: string | null;
  released_amount: string | null;
  interest_rate: string | null;
  irr_rate: string | null;
  cet_monthly_rate: string | null;
  status: string | null;
  data_quality_status: DataQuality;
  warning_count: number;
  divergence_count: number;
  funding_status: "NOT_INFORMED";
  bank_validation_status: "NOT_RECORDED";
}

export interface SaleDetail extends SaleItem {
  warnings: QualityMessage[];
  divergences: QualityMessage[];
}

export interface SalesResponse {
  items: SaleItem[];
  pagination: PageMeta;
  summary: {
    total_contracts: number;
    principal: string;
    released_amount: string;
    financed_amount: string;
    warning_contracts: number;
    divergent_contracts: number;
  };
}

export interface RevenueItem {
  id: number;
  contract_code: string | null;
  client_name: string | null;
  installment_code: string | null;
  due_date: string | null;
  payment_date: string | null;
  expected_amount: string | null;
  paid_amount: string | null;
  principal_component: string | null;
  interest_component: string | null;
  discount_amount: string | null;
  installment_status: string | null;
  situation: string | null;
  anticipation_marker: string | null;
  data_quality_status: DataQuality;
  warning_count: number;
  divergence_count: number;
}

export interface RevenueDetail extends RevenueItem {
  payment_marker: string | null;
  source_reference: string | null;
  warnings: QualityMessage[];
  divergences: QualityMessage[];
  funding_status: "NOT_INFORMED";
  bank_validation_status: "NOT_RECORDED";
}

export interface RevenueResponse {
  items: RevenueItem[];
  pagination: PageMeta;
  summary: {
    total_records: number;
    expected_amount: string;
    paid_amount: string;
    principal_received: string;
    interest_amount: string;
    discount_amount: string;
    pending_records: number;
    warning_records: number;
    divergent_records: number;
  };
}

export interface SalesFilters {
  page?: number;
  page_size?: number;
  search?: string;
  contract?: string;
  client?: string;
  status?: string;
  period_from?: string;
  period_to?: string;
  quality?: DataQuality | "";
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface RevenueFilters {
  page?: number;
  page_size?: number;
  search?: string;
  contract?: string;
  client?: string;
  status?: string;
  due_from?: string;
  due_to?: string;
  payment_from?: string;
  payment_to?: string;
  quality?: DataQuality | "";
  sort_by?: string;
  sort_order?: "asc" | "desc";
}
