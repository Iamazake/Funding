import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const pageNames = ["InvestorsPage.tsx", "InvestorDetailPage.tsx", "ContributionsPage.tsx", "ContributionDetailPage.tsx", "SalesPages.tsx"];
const revenuePageNames = ["RevenuePage.tsx", "RevenueDetailPage.tsx"];

describe("telas reais de investidores e aportes", () => {
  it.each(pageNames)("%s não usa mocks nem localStorage", (pageName) => {
    const path = fileURLToPath(new URL(`./${pageName}`, import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toContain("fundingApi");
    expect(source).not.toMatch(/demoFundingState|fundingRepository|useFundingState|localStorage/i);
  });

  it("detalhe de Vendas exibe estados e múltiplas fontes reais", () => {
    const path = fileURLToPath(new URL("./SalesPages.tsx", import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toContain("Funding ainda não informado.");
    expect(source).toContain("composition.allocations.map");
    expect(source).toContain("fundingApi.createAllocation");
    expect(source).toContain("fundingApi.reverseAllocation");
    expect(source).toContain("fundingApi.registerRemoCapital");
    expect(source).toContain('min-w-[1160px]');
    expect(source).toContain('Parcela (PMT)');
    expect(source).not.toContain('min-w-[1500px]');
  });

  it.each(revenuePageNames)("%s não usa mocks nem localStorage", (pageName) => {
    const path = fileURLToPath(new URL(`./${pageName}`, import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toMatch(/operationalApi|fundingApi/);
    expect(source).not.toMatch(/demoFundingState|fundingRepository|useFundingState|localStorage/i);
  });

  it("rateio real cobre estados, múltiplas fontes, capital REMO e gap", () => {
    const panelPath = fileURLToPath(new URL("../components/funding/RevenueFundingPanel.tsx", import.meta.url));
    const detailPath = fileURLToPath(new URL("./RevenueDetailPage.tsx", import.meta.url));
    const panel = readFileSync(panelPath, "utf8");
    const detail = readFileSync(detailPath, "utf8");
    expect(panel).toContain("PENDING_FUNDING");
    expect(panel).toContain("READY");
    expect(panel).toContain("DISTRIBUTED");
    expect(panel).toContain("DIVERGENT");
    expect(panel).toContain("REVERSED");
    expect(panel).toContain("Capital REMO");
    expect(panel).toContain("Não identificado");
    expect(panel).toContain("distribution.items.map");
    expect(detail).toContain("fundingApi.distributeRevenue");
    expect(detail).toContain("fundingApi.reverseRevenueDistribution");
  });

  it("shell e configurações descrevem as integrações reais", () => {
    const shellPath = fileURLToPath(new URL("../components/app/AdminShell.tsx", import.meta.url));
    const settingsPath = fileURLToPath(new URL("./SettingsPage.tsx", import.meta.url));
    const source = `${readFileSync(shellPath, "utf8")}\n${readFileSync(settingsPath, "utf8")}`;
    expect(source).toContain("Integração real · API + Supabase");
    expect(source).toContain("Investidores, Aportes, Vendas e Receita");
    expect(source).not.toContain("Dados fictícios · localStorage");
    expect(source).not.toContain("Sem Excel · Sem Supabase");
    expect(source).not.toContain("Somente mocks fictícios");
  });

  it("modal de alocação limita o teste local pelo saldo atual", () => {
    const modalPath = fileURLToPath(new URL("../components/funding/SaleFundingAllocationModal.tsx", import.meta.url));
    const source = readFileSync(modalPath, "utf8");
    expect(source).toContain("import.meta.env.DEV");
    expect(source).toContain("Modo de teste:");
    expect(source).toContain("saldo atual como limite");
    expect(source).toContain("Produção continua protegida pelo saldo histórico");
  });

  it("detalhe do aporte usa a análise real com operações, ledger e retornos", () => {
    const path = fileURLToPath(new URL("./ContributionDetailPage.tsx", import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toContain("fundingApi.getContributionAnalysis");
    expect(source).toContain("Operações financiadas");
    expect(source).toContain("Movimentações");
    expect(source).toContain("Retornos");
    expect(source).toContain("Nenhum retorno de Receita processado para este aporte.");
    expect(source).toContain("loan_id");
    expect(source).toContain("Informação econômica; não altera o saldo");
    expect(source).not.toMatch(/demoFundingState|fundingRepository|localStorage/i);
  });

  it("Tesouraria usa caixa real sem mocks, localStorage ou dupla contagem", () => {
    const path = fileURLToPath(new URL("./TreasuryPage.tsx", import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toContain("treasuryApi.getSummary");
    expect(source).toContain("treasuryApi.listMovements");
    expect(source).toContain("Fluxo líquido conhecido");
    expect(source).toContain("não representa saldo bancário conciliado");
    expect(source).toContain("TreasuryValidationModal");
    expect(source).toContain("Pendentes de validação");
    expect(source).toContain("DIVERGENT");
    expect(source).not.toMatch(/demoFundingState|fundingRepository|useFundingState|localStorage/i);
    expect(source).not.toMatch(/PRINCIPAL_RETURN|allocationReceiptShares/i);
  });

  it("modal bancário calcula status, diferença, justificativa e histórico", () => {
    const path = fileURLToPath(new URL("../components/funding/TreasuryValidationModal.tsx", import.meta.url));
    const source = readFileSync(path, "utf8");
    expect(source).toContain("treasuryValidationPreview");
    expect(source).toContain("Justificativa");
    expect(source).toContain("Diferença banco − sistema");
    expect(source).toContain("Histórico de validações");
    expect(source).toContain("treasuryApi.validateMovement");
    expect(source).not.toMatch(/localStorage|demoFundingState/i);
  });

  it("Vendas e Receita usam a validação bancária operacional compartilhada sem mocks", () => {
    const sharedPath = fileURLToPath(new URL("../components/funding/OperationalBankValidationPage.tsx", import.meta.url));
    const salesPath = fileURLToPath(new URL("./SalesPages.tsx", import.meta.url));
    const revenuePath = fileURLToPath(new URL("./TreasuryIncomingPages.tsx", import.meta.url));
    const shared = readFileSync(sharedPath, "utf8");
    const routes = `${readFileSync(salesPath, "utf8")}\n${readFileSync(revenuePath, "utf8")}`;
    expect(routes).toContain('kind="SALE"');
    expect(routes).toContain('kind="REVENUE"');
    expect(shared).toContain("treasuryApi.getSummary");
    expect(shared).toContain("treasuryApi.listMovements");
    expect(shared).toContain("TreasuryValidationModal");
    expect(shared).toContain("installment");
    expect(shared).toContain("validation_status");
    expect(`${shared}\n${routes}`).not.toMatch(/CTR-DEMO-1001|Cliente A\*\*\*|Tesouraria Demo|demoFundingState|fundingRepository|localStorage/i);
  });
});
