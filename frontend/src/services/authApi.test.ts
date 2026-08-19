import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import { canAccessPath } from "@/lib/accessControl";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api";
import { AuthApiError, authApi } from "@/services/authApi";

afterEach(() => vi.restoreAllMocks());

describe("autenticação e acesso", () => {
  it("faz login e /me usando somente cookie HttpOnly", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ user: { role: "ADMIN" }, expires_at: "2026-08-19T00:00:00Z" }), { status: 200 }),
    );
    await authApi.login("admin@remo.local", "senha segura");
    await authApi.me();
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ credentials: "include", method: "POST" }));
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ credentials: "include" }));
    const sources = ["authApi.ts", "../contexts/AuthContext.tsx"].map((relative) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8")).join("\n");
    expect(sources).not.toMatch(/localStorage|sessionStorage/);
  });

  it("propaga credencial inválida e erro de conexão sem revelar o e-mail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ detail: "E-mail ou senha inválidos." }), { status: 401 }));
    await expect(authApi.login("inexistente@remo.local", "incorreta")).rejects.toMatchObject({ status: 401, message: "E-mail ou senha inválidos." });
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("network"));
    await expect(authApi.me()).rejects.toEqual(new AuthApiError("Não foi possível conectar ao servidor.", null));
  });

  it("encerra a sessão no backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await authApi.logout();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/auth/logout"), expect.objectContaining({ method: "POST", credentials: "include" }));
  });

  it("envia o cookie em toda a gestão ADMIN", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify([]), { status: 200 }),
    );
    await authApi.listUsers();
    await authApi.createUser({ name: "Analista", email: "analista@remo.local", password: "senha temporaria", role: "ANALYST" });
    await authApi.updateUser("user-id", { status: "INACTIVE" });
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await authApi.resetPassword("user-id", "outra senha segura");
    expect(fetchMock.mock.calls).toHaveLength(4);
    fetchMock.mock.calls.forEach((call) => expect(call[1]).toEqual(expect.objectContaining({ credentials: "include" })));
  });

  it("um 401 administrativo invalida imediatamente o estado visual", async () => {
    const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
    const events = new EventTarget(); let notified = false;
    events.addEventListener(AUTH_UNAUTHORIZED_EVENT, () => { notified = true; });
    Object.defineProperty(globalThis, "window", { value: events, configurable: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Autenticação necessária." }), { status: 401 }));
    try { await expect(authApi.listUsers()).rejects.toMatchObject({ status: 401 }); } finally {
      if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
      else Reflect.deleteProperty(globalThis, "window");
    }
    expect(notified).toBe(true);
  });

  it("matriz visual preserva operação do ANALYST e restringe administração", () => {
    expect(canAccessPath("ANALYST", "/vendas")).toBe(true);
    expect(canAccessPath("ANALYST", "/receita")).toBe(true);
    expect(canAccessPath("ANALYST", "/tesouraria")).toBe(true);
    expect(canAccessPath("ANALYST", "/configuracoes/usuarios")).toBe(false);
    expect(canAccessPath("ADMIN", "/configuracoes/usuarios")).toBe(true);
  });

  it("possui tela de login, rota protegida, menus por perfil e gestão ADMIN", () => {
    const files = ["../pages/LoginPage.tsx", "../App.tsx", "../components/app/AdminShell.tsx", "../pages/UsersPage.tsx", "../contexts/AuthContext.tsx"];
    const source = files.map((relative) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8")).join("\n");
    expect(source).toContain("E-mail ou senha inválidos.");
    expect(source).toContain('navigate("/login"');
    expect(source).toContain("adminOnly");
    expect(source).toContain("Novo usuário");
    expect(source).toContain("Redefinir senha");
    expect(source).toContain("Sair");
    expect(source).toContain("const confirmedUser = await authApi.me()");
  });
});
