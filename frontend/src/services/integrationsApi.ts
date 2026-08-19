import { API_URL, notifyIfUnauthorized } from "@/lib/api";
import type {
  OneDriveConnectResponse,
  OperationalBatchDetail,
  OperationalBatchPromotionResponse,
  OperationalBatchSummary,
  OperationalSourceStatus,
  OperationalSyncResponse,
} from "@/types/integrations";

export class IntegrationApiError extends Error {
  constructor(message: string, readonly status: number | null) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new IntegrationApiError("Não foi possível conectar ao servidor.", null);
  }
  notifyIfUnauthorized(response.status);
  if (!response.ok) {
    let message = "Não foi possível concluir a operação com o OneDrive.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Preserve the safe generic error.
    }
    throw new IntegrationApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const prefix = "/api/integrations/onedrive";

export const integrationsApi = {
  status: () => request<OperationalSourceStatus>(`${prefix}/status`),
  connect: () => request<OneDriveConnectResponse>(`${prefix}/connect`, { method: "POST" }),
  disconnect: () => request<void>(`${prefix}/disconnect`, { method: "POST" }),
  checkUpdate: () => request<OperationalSourceStatus>(`${prefix}/check`, { method: "POST" }),
  synchronize: () => request<OperationalSyncResponse>(`${prefix}/sync`, { method: "POST" }),
  listBatches: () => request<{ items: OperationalBatchSummary[] }>("/api/operational/batches"),
  getBatch: (batchId: number) =>
    request<OperationalBatchDetail>(`/api/operational/batches/${batchId}`),
  promoteBatch: (batchId: number) =>
    request<OperationalBatchPromotionResponse>(`/api/operational/batches/${batchId}/promote`, {
      method: "POST",
    }),
};
