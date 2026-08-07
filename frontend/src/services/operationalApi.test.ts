import { afterEach, describe, expect, it, vi } from "vitest";

import { decimalToCents, formatOperationalMoney } from "@/lib/operationalFormat";
import {
  collectionView,
  getRevenue,
  getRevenueDetail,
  getSale,
  getSales,
} from "@/services/operationalApi";

function response(payload: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => payload } as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("provider operacional real", () => {
  it("carrega Vendas com paginação e filtros server-side", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      items: [{ id: "contract:1", warning_count: 2, divergence_count: 0, funding_status: "NOT_INFORMED" }],
      pagination: { page: 2, page_size: 25, total: 1459, pages: 59 },
      summary: { total_contracts: 1459 },
    }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await getSales({ page: 2, page_size: 25, contract: "CTR", quality: "WARNING" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/api/operational/sales?");
    expect(url).toContain("page=2");
    expect(url).toContain("contract=CTR");
    expect(url).toContain("quality=WARNING");
    expect(result.items[0].warning_count).toBe(2);
    expect(result.items[0]).not.toHaveProperty("investor");
    expect(result.items[0]).not.toHaveProperty("cpf");
  });

  it("carrega detalhe de Venda sem funding fictício", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      id: "loan:3",
      funding_status: "NOT_INFORMED",
      bank_validation_status: "NOT_RECORDED",
      warnings: [],
      divergences: [{ severity: "DIVERGENT", message: "Empréstimo sem contrato correspondente." }],
    }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await getSale("loan:3");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/operational/sales/loan%3A3");
    expect(result.funding_status).toBe("NOT_INFORMED");
    expect(result.divergences[0].severity).toBe("DIVERGENT");
  });

  it("carrega Receita, preserva linhas repetidas e aplica filtros", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      items: [
        { id: 10, contract_code: "CTR-1", installment_code: "2", warning_count: 1 },
        { id: 11, contract_code: "CTR-1", installment_code: "2", warning_count: 0 },
      ],
      pagination: { page: 1, page_size: 25, total: 2, pages: 1 },
      summary: { total_records: 2 },
    }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await getRevenue({ contract: "CTR-1", payment_from: "2026-01-01" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("contract=CTR-1");
    expect(url).toContain("payment_from=2026-01-01");
    expect(result.items).toHaveLength(2);
    expect(new Set(result.items.map((item) => item.id)).size).toBe(2);
  });

  it("carrega detalhe de Receita com warning, divergência e marcador preservado", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      id: 30,
      payment_marker: "I",
      warnings: [{ severity: "WARNING", message: "Valor ambíguo." }],
      divergences: [{ severity: "DIVERGENT", message: "Parcela sem empréstimo." }],
      funding_status: "NOT_INFORMED",
    })));
    const result = await getRevenueDetail(30);
    expect(result.payment_marker).toBe("I");
    expect(result.warnings).toHaveLength(1);
    expect(result.divergences).toHaveLength(1);
  });

  it("não faz fallback silencioso quando a API falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, false, 503)));
    await expect(getSales()).rejects.toThrow("Não foi possível conectar à API operacional.");
  });
});

describe("estados e dinheiro operacional", () => {
  it("distingue loading, erro, vazio, filtro vazio e sucesso", () => {
    expect(collectionView("loading", 0, false)).toBe("loading");
    expect(collectionView("error", 0, false)).toBe("error");
    expect(collectionView("success", 0, false)).toBe("empty");
    expect(collectionView("success", 0, true)).toBe("filtered-empty");
    expect(collectionView("success", 1, false)).toBe("success");
  });

  it("converte decimal monetário em centavos sem ponto flutuante", () => {
    expect(decimalToCents("1234.56")).toBe("123456");
    expect(decimalToCents("-0.05")).toBe("-5");
    expect(formatOperationalMoney("1234.56")).toContain("1.234,56");
  });
});
