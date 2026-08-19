import { afterEach, describe, expect, it, vi } from "vitest";

import { treasuryApi } from "@/services/treasuryApi";

afterEach(() => vi.restoreAllMocks());

describe("treasuryApi", () => {
  it("consulta resumo e movimentos reais com filtros", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const payload = url.includes("/summary")
        ? { known_net_flow: "82000.00" }
        : { items: [], pagination: { page: 1, page_size: 50, total: 0, pages: 0 } };
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    await treasuryApi.getSummary({ period_from: "2026-01-01", movement_type: "REVENUE" });
    await treasuryApi.listMovements({ page: 2, page_size: 25, search: "CTR 001" });
    expect(String(fetchMock.mock.calls[0][0])).toContain("period_from=2026-01-01");
    expect(String(fetchMock.mock.calls[0][0])).toContain("movement_type=REVENUE");
    expect(String(fetchMock.mock.calls[1][0])).toContain("search=CTR+001");
  });

  it("consulta detalhe por identidade estável", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "sale:loan:40" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await treasuryApi.getMovement("sale:loan:40");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/movements/sale%3Aloan%3A40");
  });

  it("propaga erro explícito sem fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Tesouraria indisponível." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(treasuryApi.getSummary()).rejects.toThrow("Tesouraria indisponível.");
  });

  it("consulta, cria e preserva histórico de validação", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ status: "VALIDATED", items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await treasuryApi.getValidation("revenue:30");
    await treasuryApi.validateMovement("revenue:30", {
      observed_amount: "260.53",
      observed_date: "2026-08-18",
      bank_reference: null,
      justification: null,
    });
    await treasuryApi.getValidationHistory("revenue:30");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/revenue%3A30/validation");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({
      method: "POST",
      body: expect.stringContaining('"observed_amount":"260.53"'),
    }));
    expect(String(fetchMock.mock.calls[2][0])).toContain("/validation-history");
  });
});
