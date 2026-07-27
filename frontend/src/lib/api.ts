const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

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

