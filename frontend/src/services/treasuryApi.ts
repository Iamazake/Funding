import { API_URL, notifyIfUnauthorized } from "@/lib/api";
import type {
  TreasuryFilters,
  TreasuryMovement,
  TreasuryMovementsPage,
  TreasurySummary,
  TreasuryValidation,
  TreasuryValidationHistory,
  TreasuryValidationInput,
  TreasuryValidationState,
} from "@/types/treasuryApi";

function queryString(filters: TreasuryFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/treasury${path}`, {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init?.headers },
  });
  notifyIfUnauthorized(response.status);
  if (!response.ok) {
    let message = "Não foi possível carregar a Tesouraria real.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Preserve the friendly API error.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const treasuryApi = {
  getSummary: (filters: TreasuryFilters = {}) =>
    request<TreasurySummary>(`/summary${queryString(filters)}`),
  listMovements: (filters: TreasuryFilters = {}) =>
    request<TreasuryMovementsPage>(`/movements${queryString(filters)}`),
  getMovement: (id: string) =>
    request<TreasuryMovement>(`/movements/${encodeURIComponent(id)}`),
  getValidation: (id: string) =>
    request<TreasuryValidationState>(`/movements/${encodeURIComponent(id)}/validation`),
  validateMovement: (id: string, input: TreasuryValidationInput) =>
    request<TreasuryValidation>(`/movements/${encodeURIComponent(id)}/validation`, {
      method: "POST",
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
    }),
  getValidationHistory: (id: string) =>
    request<TreasuryValidationHistory>(`/movements/${encodeURIComponent(id)}/validation-history`),
};
