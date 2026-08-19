export type ConnectionStatus = "CONNECTED" | "DISCONNECTED" | "RECONNECT_REQUIRED" | "FILE_NOT_FOUND";
export type UpdateStatus =
  | "UNKNOWN"
  | "CURRENT"
  | "UPDATE_AVAILABLE"
  | "FILE_NOT_FOUND"
  | "RECONNECT_REQUIRED"
  | "ERROR";

export interface OperationalSourceStatus {
  source_type: "local" | "onedrive";
  connection_status: ConnectionStatus;
  update_status: UpdateStatus;
  file_name: string | null;
  file_path: string | null;
  size: number | null;
  modified_at: string | null;
  last_checked_at: string | null;
  last_sync_at: string | null;
  last_sync_sha256: string | null;
  last_batch_id: number | null;
  message: string;
}

export interface OneDriveConnectResponse {
  authorization_url: string;
  expires_at: string;
}

export interface OperationalSyncResponse {
  sync_run_id: number;
  import_batch_id: number | null;
  status: string;
  counters: Record<string, unknown>;
  message: string;
}

export interface BatchUser {
  id: string;
  name: string;
}

export interface BatchDataCounts {
  bcli_cadastro: number;
  dfen_contrato: number;
  econ_emprestimos: number;
  econ_amortizacoes: number;
}

export interface BatchQualityCounts {
  valid: number;
  warning: number;
  divergent: number;
  invalid: number;
}

export interface BatchPromotionInfo {
  id: number;
  is_current: boolean;
  promoted_at: string;
  promoted_by: BatchUser | null;
}

export interface OperationalBatchSummary {
  id: number;
  sync_run_id: number;
  started_at: string;
  completed_at: string | null;
  source_type: "LOCAL" | "ONEDRIVE";
  source_name: string | null;
  source_size: number | null;
  source_sha256: string;
  status: string;
  data_counts: BatchDataCounts;
  quality_counts: BatchQualityCounts;
  initiated_by: BatchUser | null;
  promotion: BatchPromotionInfo | null;
}

export interface BatchCountComparison {
  current: number;
  candidate: number;
  difference: number;
}

export interface OperationalBatchDetail extends OperationalBatchSummary {
  comparison: {
    current_promotion_id: number | null;
    current_source_batch_id: number | null;
    clients: BatchCountComparison;
    contracts: BatchCountComparison;
    loans: BatchCountComparison;
    installments: BatchCountComparison;
    sales: BatchCountComparison;
    revenue: BatchCountComparison;
  };
  promotion_eligible: boolean;
  promotion_eligibility_reason: string;
}

export interface OperationalBatchPromotionResponse {
  promotion_id: number;
  source_batch_id: number;
  status: string;
  idempotent: boolean;
  summary: Record<string, unknown>;
}
