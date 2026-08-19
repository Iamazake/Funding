// Same-origin is the production default. VITE_API_URL remains an explicit
// escape hatch for split-origin development or a separately hosted API.
export const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const AUTH_UNAUTHORIZED_EVENT = "funding-auth-unauthorized";

export function notifyIfUnauthorized(status: number): void {
  if (status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
  }
}

export type HealthResponse = {
  status: "ok" | "error";
  api: "ok";
  database: "connected" | "unavailable";
};

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/health`, { signal });

  if (!response.ok) {
    throw new Error("Health check failed");
  }

  return (await response.json()) as HealthResponse;
}
