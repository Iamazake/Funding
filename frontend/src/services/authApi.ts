import { API_URL, notifyIfUnauthorized } from "@/lib/api";
import type { AppUser, LoginResponse, UserCreateInput, UserUpdateInput } from "@/types/auth";

export class AuthApiError extends Error {
  constructor(message: string, readonly status: number | null) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  notifyUnauthorized = true,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: init?.body
        ? { "Content-Type": "application/json", Accept: "application/json", ...init.headers }
        : { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new AuthApiError("Não foi possível conectar ao servidor.", null);
  }
  if (notifyUnauthorized) notifyIfUnauthorized(response.status);
  if (!response.ok) {
    let message = "Não foi possível concluir a operação.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep the generic error without exposing internals.
    }
    throw new AuthApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const authApi = {
  login: (email: string, password: string) => request<LoginResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false),
  me: () => request<AppUser>("/api/auth/me"),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  listUsers: () => request<AppUser[]>("/api/admin/users"),
  createUser: (input: UserCreateInput) => request<AppUser>("/api/admin/users", { method: "POST", body: JSON.stringify(input) }),
  updateUser: (id: string, input: UserUpdateInput) => request<AppUser>(`/api/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(input) }),
  resetPassword: (id: string, newPassword: string) => request<void>(`/api/admin/users/${encodeURIComponent(id)}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: newPassword }) }),
};
