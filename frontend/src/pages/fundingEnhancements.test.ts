import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { formatPercentage } from "@/lib/formatters";
import { formatMonthlyRate } from "@/lib/fundingFormat";

const source = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

describe("evoluções incrementais do Funding", () => {
  it("limita percentuais visualmente a quatro casas", () => {
    expect(formatPercentage("12.3456789")).toBe("12,3457%");
    expect(formatPercentage("2.0000000")).toBe("2%");
    expect(formatMonthlyRate("0.0234567890")).toBe("2,3457% a.m.");
  });

  it("Receita exibe KPIs, cliente, principal e validação sem coluna Parcela", () => {
    const page = source("./RevenuePage.tsx");
    expect(page).toContain("Principal Total");
    expect(page).toContain("Principal Aberto");
    expect(page).toContain("PMT em Atraso");
    expect(page).toContain("% Inadimplência");
    expect(page).toContain("Regra provisória · PMT vencida ÷ PMT aberta");
    expect(page).toContain("Cliente / contrato");
    expect(page).toContain("Principal");
    expect(page).toContain("Validação");
    expect(page).not.toContain("<TableHead>Parcela</TableHead>");
    expect(page).toContain("hidden md:block");
    expect(page).toContain("md:hidden");
  });

  it("organiza Vendas e Receita por cliente com fallback e layout responsivo", () => {
    const sales = source("./SalesPages.tsx");
    const revenue = source("./RevenuePage.tsx");
    for (const page of [sales, revenue]) {
      expect(page).toContain("Cliente / contrato");
      expect(page).toContain('|| "Não informado"');
      expect(page).toContain("max-w-[230px] truncate");
      expect(page).toContain("hidden md:block");
      expect(page).toContain("md:hidden");
    }
    expect(sales).toContain('placeholder="Contrato ou cliente"');
    expect(revenue).toContain('placeholder="Contrato, cliente ou parcela"');
  });

  it("Receita oferece relevância operacional, cinco chips e ordenações explícitas", () => {
    const page = source("./RevenuePage.tsx");
    for (const label of ["Todos", "Recebidos", "Em aberto", "Em atraso", "Futuros"]) expect(page).toContain(label);
    expect(page).toContain('sort_by: "operational_relevance"');
    expect(page).toContain("Relevância operacional");
    expect(page).toContain("Vencimento mais próximo");
    expect(page).toContain("Vencimento mais distante");
    expect(page).toContain("Pagamento mais recente");
    expect(page).toContain("Pagamento mais antigo");
  });

  it("detalhe da Receita usa observação operacional e oculta Referência", () => {
    const detail = source("./RevenueDetailPage.tsx");
    expect(detail).toContain("Observação operacional");
    expect(detail).toContain("anticipation_marker");
    expect(detail).toContain("Não informado");
    expect(detail).not.toContain("Referência operacional");
  });

  it("cadastros expõem documento, telefone, data do aporte e vencimento", () => {
    const investor = source("../components/funding/InvestorFormModal.tsx");
    const contribution = source("../components/funding/ContributionFormModal.tsx");
    expect(investor).toContain("Nome completo ou razão social");
    expect(investor).toContain("CPF ou CNPJ");
    expect(investor).toContain("Telefone com DDD");
    expect(contribution).toContain("Data do aporte");
    expect(contribution).toContain("Data fim");
    expect(contribution).toContain("não registra devolução automática");
  });

  it("validação bancária persiste códigos estáveis e não mostra Referência", () => {
    const modal = source("../components/funding/TreasuryValidationModal.tsx");
    for (const label of ["Banco Inter", "Banco BTG", "PicPay", "Nubank", "C6 Bank", "Dinheiro"]) expect(modal).toContain(label);
    expect(modal).toContain("bank_code");
    expect(modal).not.toContain('label="Referência');
  });

  it("REFIN e RENEG são criados no cockpit bancário e detalhes preservam correção auditada", () => {
    const sales = source("./SalesPages.tsx");
    const cockpit = source("../components/funding/TreasuryValidationModal.tsx");
    const modal = source("../components/funding/RefinancingModal.tsx");
    expect(sales).toContain('user?.role === "ADMIN"');
    expect(sales).not.toContain("debtContinuityApi.createRefinancing");
    expect(sales).toContain("debtContinuityApi.correctRefinancing");
    expect(sales).toContain("Corrigir vínculo");
    expect(sales).toContain("Refinanciado para →");
    expect(sales).toContain("Renegociado para →");
    expect(sales).toContain("Renegociado de");
    expect(cockpit).toContain("NORMAL");
    expect(cockpit).toContain("REFINANCIAMENTO");
    expect(cockpit).toContain("RENEGOCIAÇÃO");
    expect(cockpit).toContain("debtContinuityApi.createRefinancing");
    expect(cockpit).toContain("debtContinuityApi.createRenegotiationReview");
    expect(cockpit).toContain("debtContinuityApi.confirmRenegotiation");
    expect(cockpit).toContain("has_new_disbursement: false");
    expect(cockpit).toContain("Nenhuma validação bancária de R$ 0");
    expect(cockpit).toContain("REFIN exige released_amount operacional maior que zero");
    expect(modal).toContain("nova liberação real operacional");
    expect(modal).toContain("Reprogramação sem dinheiro novo é RENEGOTIATION");
  });

  it("Receita e Vendas classificam a mesma venda canônica no cockpit compartilhado", () => {
    const cockpit = source("../components/funding/TreasuryValidationModal.tsx");
    const queue = source("../components/funding/OperationalBankValidationPage.tsx");
    expect(queue).toContain("OperationTypeBadge");
    expect(queue).toContain('kind === "SALE"');
    expect(queue).toContain('kind === "REVENUE"');
    expect(cockpit).toContain('movement?.sale_id');
    expect(cockpit).toContain("getSale(canonicalSaleId)");
    expect(cockpit).toContain("isSale || isRevenue");
    expect(cockpit).toContain("Continuidade canônica confirmada");
    expect(cockpit).toContain("compartilhada com Vendas");
    expect(cockpit).toContain("hasConfirmedContinuity");
  });

  it("Receita mantém caixa bancário independente e REFIN usa somente released_amount operacional", () => {
    const cockpit = source("../components/funding/TreasuryValidationModal.tsx");
    expect(cockpit).toContain("canonicalSale?.released_amount ?? movement?.released_amount ?? null");
    expect(cockpit).not.toContain("Boolean(movement?.amount && Number(movement.amount) > 0)");
    expect(cockpit).toContain('if (isSale) {');
    expect(cockpit).toContain("A classificação da continuidade não valida este recebimento no banco");
    expect(cockpit).toContain("Recebimento desta parcela");
    expect(cockpit).toContain("has_new_disbursement: false");
    expect(cockpit).not.toMatch(/FundingAllocation|FundingLedgerEntry/);
  });

  it("Vendas e Receita selecionam múltiplos predecessores no mesmo cockpit", () => {
    const cockpit = source("../components/funding/TreasuryValidationModal.tsx");
    expect(cockpit).toContain("Contratos anteriores selecionados:");
    expect(cockpit).toContain("Buscar contratos anteriores");
    expect(cockpit).toContain("Contrato ou cliente");
    expect(cockpit).toContain("predecessorIds.map");
    expect(cockpit).toContain("predecessor_sale_identity_ids");
    expect(cockpit).toContain("candidate_predecessor_sale_identity_ids");
    expect(cockpit).toContain("client_identity_id === successorClientIdentityId");
    expect(cockpit).toContain("Desmarcar");
    expect(cockpit).toContain("Remover");
  });

  it("preserva BOL_ANTECIP como observação e trata ausências de forma amigável", () => {
    const detail = source("./RevenueDetailPage.tsx");
    expect(detail).toContain("Observação operacional");
    expect(detail).toContain('row.anticipation_marker ?? "Não informado"');
    expect(detail).toContain('row.client_name ?? "Não informado"');
  });
});
