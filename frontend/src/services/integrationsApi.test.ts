import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import { integrationsApi } from "@/services/integrationsApi";
import { onedriveOAuthErrorMessage } from "@/lib/onedriveOAuth";

afterEach(() => vi.restoreAllMocks());

describe("integração OneDrive", () => {
  it("usa cookie e nunca recebe tokens Microsoft", async () => {
    const payload = {
      source_type: "onedrive", connection_status: "CONNECTED", update_status: "CURRENT",
      file_name: "Cadastro de Clientes.xlsm", file_path: "/pasta/Cadastro de Clientes.xlsm",
      size: 10, modified_at: null, last_checked_at: null, last_sync_at: null,
      last_sync_sha256: null, last_batch_id: null, message: "OneDrive conectado.",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    const result = await integrationsApi.status();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/integrations/onedrive/status"), expect.objectContaining({ credentials: "include" }));
    expect(JSON.stringify(result)).not.toMatch(/access_token|refresh_token|token_cache/i);
  });

  it("mantém verificação e sincronização como ações distintas", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ message: "ok", counters: {}, status: "succeeded", sync_run_id: 3, import_batch_id: 3 }), { status: 200 }),
    );
    await integrationsApi.checkUpdate();
    await integrationsApi.synchronize();
    expect(fetchMock.mock.calls[0][0]).toContain("/check");
    expect(fetchMock.mock.calls[1][0]).toContain("/sync");
    fetchMock.mock.calls.forEach((call) => expect(call[1]).toEqual(expect.objectContaining({ method: "POST" })));
  });

  it("expõe revisão e promoção como chamadas administrativas separadas", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await integrationsApi.listBatches();
    await integrationsApi.getBatch(3);
    await integrationsApi.promoteBatch(3);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/operational/batches");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/operational/batches/3");
    expect(fetchMock.mock.calls[2][0]).toContain("/api/operational/batches/3/promote");
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ method: "POST" }));
  });

  it("representa todos os estados e controles administrativos na tela", () => {
    const source = readFileSync(
      fileURLToPath(new URL("../pages/SyncPage.tsx", import.meta.url)),
      "utf8",
    );
    ["Não conectado", "Nova versão disponível", "Atualizado", "Reconexão necessária", "Arquivo não encontrado"].forEach((label) => expect(source).toContain(label));
    ["Conectar OneDrive", "Verificar atualização", "Sincronizar", "Desconectar"].forEach((label) => expect(source).toContain(label));
    ["Histórico de sincronizações / Batches", "Revisar", "Promover batch"].forEach((label) => expect(source).toContain(label));
    expect(source).toContain("Esta ação tornará este batch a versão operacional utilizada por Vendas e Receita.");
    expect(source).toContain("nunca promove dados automaticamente");
  });

  it("traduz somente códigos OAuth sanitizados em mensagens administrativas", () => {
    expect(onedriveOAuthErrorMessage("invalid_client_secret")).toContain("Value do secret");
    expect(onedriveOAuthErrorMessage("redirect_uri_mismatch")).toContain("redirect URI");
    expect(onedriveOAuthErrorMessage("file_not_found")).toContain("arquivo oficial");
    expect(onedriveOAuthErrorMessage("graph_permission_denied")).toContain("leitura");
    expect(onedriveOAuthErrorMessage("unexpected-provider-detail")).toBe(
      "Não foi possível concluir a autorização Microsoft.",
    );
  });
});
