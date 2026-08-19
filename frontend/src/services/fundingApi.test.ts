import { afterEach, describe, expect, it, vi } from "vitest";

import { fundingApi } from "@/services/fundingApi";

afterEach(() => vi.restoreAllMocks());

describe("fundingApi", () => {
  it("usa somente a API real para listar investidores", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }));
    await expect(fundingApi.listInvestors()).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith("/api/funding/investors", expect.objectContaining({ headers: undefined }));
  });

  it("envia dinheiro e taxa como strings decimais determinísticas", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ id: "1" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    await fundingApi.createContribution({ investor_id: "investor", contribution_date: "2026-08-11", original_amount: "1234.56", monthly_rate: "0.0200000000", status: "ACTIVE", notes: null });
    expect(fetch).toHaveBeenCalledWith("/api/funding/contributions", expect.objectContaining({ method: "POST", body: expect.stringContaining('"monthly_rate":"0.0200000000"') }));
  });

  it("propaga erro da API sem fallback para mock", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Banco indisponível." }), { status: 503, headers: { "Content-Type": "application/json" } }));
    await expect(fundingApi.listInvestors()).rejects.toThrow("Banco indisponível.");
  });

  it("carrega composição real inclusive para Venda órfã", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ sale_id: "loan:40", funding_status: "INCOMPLETE", operation_amount: "600.00", identified_amount: "500.00", difference: "100.00", source_count: 2, allocations: [{ id: "a" }, { id: "b" }] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const result = await fundingApi.getSaleComposition("loan:40");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/sales/loan%3A40/composition");
    expect(result.funding_status).toBe("INCOMPLETE");
    expect(result.allocations).toHaveLength(2);
  });

  it("registra allocation e reversão por eventos explícitos", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ funding_status: "COMPLETE", allocations: [] }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await fundingApi.createAllocation("contract:10", { source_id: "source", amount: "1000.00", notes: null });
    await fundingApi.reverseAllocation("allocation", { reason: "Correção" });
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "POST", body: expect.stringContaining('"amount":"1000.00"') }));
    expect(String(fetchMock.mock.calls[1][0])).toContain("/allocations/allocation/reversal");
  });

  it("consulta, processa e reverte rateio real da Receita", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ status: "DISTRIBUTED", items: [], unidentified_principal: "200.00" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await fundingApi.getRevenueDistribution(10);
    await fundingApi.distributeRevenue(10, { notes: null });
    await fundingApi.reverseRevenueDistribution("distribution", { reason: "Correção" });
    expect(String(fetchMock.mock.calls[0][0])).toContain("/revenue/10/distribution");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: "POST", body: '{"notes":null}' }));
    expect(String(fetchMock.mock.calls[1][1]?.body)).not.toContain("actor");
    expect(String(fetchMock.mock.calls[2][0])).toContain("/revenue/distributions/distribution/reversal");
  });

  it("carrega a análise agregada do aporte sem fallback", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ summary: { available_balance: "7000.00" }, operations: [], movements: [], returns: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await fundingApi.getContributionAnalysis("aporte:real");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/contributions/aporte%3Areal/analysis");
    expect(result.summary.available_balance).toBe("7000.00");
    expect(result.operations).toEqual([]);
  });
});
