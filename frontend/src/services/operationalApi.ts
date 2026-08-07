import { API_URL } from "@/lib/api";
import type {
  RevenueDetail,
  RevenueFilters,
  RevenueResponse,
  SaleDetail,
  SalesFilters,
  SalesResponse,
} from "@/types/operational";

function queryString(filters: object): string {
  const params = new URLSearchParams();
  Object.entries(filters as Record<string, unknown>).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const value = params.toString();
  return value ? `?${value}` : "";
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "Registro operacional não encontrado." : "Não foi possível conectar à API operacional.");
  }
  return (await response.json()) as T;
}

export function getSales(filters: SalesFilters = {}): Promise<SalesResponse> {
  return request(`/api/operational/sales${queryString(filters)}`);
}

export function getSale(id: string): Promise<SaleDetail> {
  return request(`/api/operational/sales/${encodeURIComponent(id)}`);
}

export function getRevenue(filters: RevenueFilters = {}): Promise<RevenueResponse> {
  return request(`/api/operational/revenue${queryString(filters)}`);
}

export function getRevenueDetail(id: string | number): Promise<RevenueDetail> {
  return request(`/api/operational/revenue/${encodeURIComponent(String(id))}`);
}

export type CollectionView = "loading" | "error" | "empty" | "filtered-empty" | "success";

export function collectionView(
  status: "loading" | "error" | "success",
  total: number,
  hasFilters: boolean,
): CollectionView {
  if (status !== "success") return status;
  if (total > 0) return "success";
  return hasFilters ? "filtered-empty" : "empty";
}
