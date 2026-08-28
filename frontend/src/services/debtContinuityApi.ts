import { API_URL, notifyIfUnauthorized } from "@/lib/api";

export interface DebtContinuityResult {
  id: string;
  continuity_type: "REFINANCING" | "RENEGOTIATION" | "ROLLOVER";
  status: "REVIEW_REQUIRED" | "RENEGOTIATION_CONFIRMED" | "REFIN_CONFIRMED" | "REJECTED";
  predecessor_sale_identity_ids?: string[];
  predecessor_contract_codes?: string[];
}

export interface RefinancingInput {
  predecessor_sale_identity_id?: string;
  predecessor_sale_identity_ids?: string[];
  successor_sale_identity_id?: string;
  successor_contract_code?: string;
  effective_date: string;
  notes: string | null;
  principal_rolled: null;
}

export interface RenegotiationReviewInput {
  source_batch_id: number;
  successor_sale_identity_id: string;
  candidate_predecessor_sale_identity_ids: string[];
  continuity_type: "RENEGOTIATION";
  scope: "NEW_CONTRACT";
  effective_date: string;
  reason: string;
  evidence: Record<string, unknown>;
}

export interface RenegotiationConfirmInput {
  predecessor_sale_identity_id?: string;
  predecessor_sale_identity_ids?: string[];
  original_principal: string;
  principal_paid: string;
  principal_rolled: string;
  interest_paid: string;
  has_new_disbursement: false;
  effective_date: string;
  evidence: Record<string, unknown>;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/operational/debt-continuities${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  notifyIfUnauthorized(response.status);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail ?? "Não foi possível registrar a continuidade da dívida.");
  }
  return (await response.json()) as T;
}

const createRefinancing = (input: RefinancingInput) =>
  request<DebtContinuityResult>("/refinancings", {
    method: "POST",
    body: JSON.stringify(input),
  });

const correctRefinancing = (
  continuityId: string,
  input: Omit<RefinancingInput, "predecessor_sale_identity_id" | "principal_rolled">,
) => request<DebtContinuityResult>(`/${continuityId}/refinancing`, {
  method: "PATCH",
  body: JSON.stringify(input),
});

const createRenegotiationReview = (input: RenegotiationReviewInput) =>
  request<DebtContinuityResult>("/reviews", {
    method: "POST",
    body: JSON.stringify(input),
  });

const confirmRenegotiation = (continuityId: string, input: RenegotiationConfirmInput) =>
  request<DebtContinuityResult>(`/${continuityId}/confirm`, {
    method: "POST",
    body: JSON.stringify(input),
  });

export const debtContinuityApi = {
  createRefinancing,
  correctRefinancing,
  createRenegotiationReview,
  confirmRenegotiation,
};
