import { describe, expect, it } from "vitest";

import { cloneDemoState } from "@/data/demoFundingState";
import {
  aggregateHarvestRows, aggregateRevenueRows, buildFundingReport, buildHarvestReport,
  buildInvestorCashFlowReport, buildPddReport, buildRevenueReport, classifyPddRating, ratioBps,
  weightedAverageBps,
} from "@/lib/reports";
import { sumCents } from "@/repositories/fundingRepository";

describe("relatório Safra derivado", () => {
  it("agrega mensalmente os contratos da mesma safra", () => {
    const rows = buildHarvestReport(cloneDemoState(), { granularity: "month" });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ period: "2026-07", contractCount: 2, newContractCount: 2 });
  });

  it("agrega anualmente sem duplicar contratos", () => {
    const rows = buildHarvestReport(cloneDemoState(), { granularity: "year" });
    expect(rows).toHaveLength(1);
    expect(rows[0].period).toBe("2026");
    expect(rows[0].sourceContractIds).toHaveLength(2);
  });

  it("aplica últimos 12 e últimos 24 meses", () => {
    const state = cloneDemoState(); const template = state.fundingContracts[0];
    state.fundingContracts.push({ ...template, id: "contract-old", contractCode: "CTR-DEMO-OLD", operationDate: "2025-02-01", releaseDate: "2025-02-01" });
    const last12 = buildHarvestReport(state, { preset: "last12", asOf: "2026-08-07" });
    const last24 = buildHarvestReport(state, { preset: "last24", asOf: "2026-08-07" });
    expect(last12.flatMap((item) => item.sourceContractIds)).not.toContain("contract-old");
    expect(last24.flatMap((item) => item.sourceContractIds)).toContain("contract-old");
  });

  it("calcula principal, liberado, recebido real, a vencer, vencido e prejuízo em centavos", () => {
    const totals = aggregateHarvestRows(buildHarvestReport(cloneDemoState(), { asOf: "2026-08-07" }));
    expect(totals.principal).toBe("17000000");
    expect(totals.released).toBe("17000000");
    expect(totals.realReceipt).toBe("1250000");
    expect(totals.due).toBe("2300000");
    expect(totals.overdue).toBe("0");
    expect(totals.netLoss).toBe("30000");
    expect(totals.delinquencyBps).toBe(0);
  });

  it("calcula inadimplência pela razão vencido sobre carteira pendente", () => {
    const state = cloneDemoState(); const receipt = state.treasuryIncomingReceipts[2];
    receipt.dueDate = "2026-07-01";
    const totals = aggregateHarvestRows(buildHarvestReport(state, { asOf: "2026-08-07" }));
    expect(totals.overdue).toBe("950000");
    expect(totals.delinquencyBps).toBe(ratioBps("950000", "2300000"));
  });
});

describe("relatório Receita derivado", () => {
  it("usa exatamente os mesmos recebimentos do módulo Receita", () => {
    const state = cloneDemoState(); const rows = buildRevenueReport(state);
    const reportIds = rows.flatMap((item) => item.sourceReceiptIds);
    expect(new Set(reportIds)).toEqual(new Set(state.treasuryIncomingReceipts.map((item) => item.id)));
    expect(reportIds).toHaveLength(state.treasuryIncomingReceipts.length);
  });

  it("consolida recebimento real sem duplicar caixa", () => {
    const totals = aggregateRevenueRows(buildRevenueReport(cloneDemoState()));
    expect(totals.realReceived).toBe("1250000");
    expect(totals.installments).toBe(4);
  });
});

describe("relatório Funding derivado", () => {
  it("usa os mesmos aportes e alocações e mantém capital REMO separado", () => {
    const state = cloneDemoState(); const rows = buildFundingReport(state);
    const remo = rows.find((item) => item.kind === "REMO_OWN_CAPITAL");
    expect(remo).toMatchObject({ id: "src-remo", label: "Capital próprio REMO", investorId: undefined });
    expect(sumCents(rows.map((item) => item.allocatedCapital))).toBe(sumCents(state.contractFundingAllocations.filter((item) => !item.supersededAt).map((item) => item.amount)));
  });

  it("gera relatório filtrável por investidor a partir de seus aportes", () => {
    const row = buildFundingReport(cloneDemoState()).find((item) => item.investorId === "inv-demo-001");
    expect(row).toMatchObject({ originalCapital: "15000000", contributionIds: ["apt-demo-001", "apt-demo-002"] });
    expect(row?.contractIds).toEqual(["sale-demo-001"]);
  });
});

describe("PDD e fluxo do investidor demonstrativos", () => {
  function stateWithAllRatings() {
    const state = cloneDemoState(); const contractTemplate = state.fundingContracts[0]; const receiptTemplate = state.treasuryIncomingReceipts[0]; const entryTemplate = state.treasuryEntries.find((item) => item.type === "PMT_RECEIVED")!;
    state.fundingContracts = []; state.treasuryIncomingReceipts = []; state.treasuryEntries = [];
    const dueDates = { A: "2026-08-07", B: "2026-07-23", C: "2026-07-07", D: "2026-06-07", E: "2026-05-08", F: "2026-04-08", G: "2026-03-09", H: "2026-02-07", HH: "2026-08-30" };
    Object.entries(dueDates).forEach(([rating, dueDate], index) => {
      const contractId = `contract-${rating}`; const receiptId = `receipt-${rating}`;
      state.fundingContracts.push({ ...contractTemplate, id: contractId, contractCode: `CTR-${rating}`, maskedClientName: `Cliente ${rating}***`, principalAmount: "1000000", financedAmount: "1000000", releasedAmount: "1000000", interestRateBps: 100 + index * 10 });
      state.treasuryIncomingReceipts.push({ ...receiptTemplate, id: receiptId, fundingContractId: contractId, contractCode: `CTR-${rating}`, maskedClientName: `Cliente ${rating}***`, dueDate, expectedAmount: "100000", paidAmountFromOperationalSource: rating === "A" ? "25000" : "0", principalAmount: rating === "A" ? "25000" : "0", interestAmount: "0", iofAmount: "0", lossAmount: rating === "HH" ? "10000" : "0", status: rating === "A" ? "VALIDATED" : "WAITING_BANK_VALIDATION", bankValidationStatus: rating === "A" ? "VALIDATED" : "PENDING", reconciliationStatus: rating === "A" ? "RECONCILED" : "PENDING" });
      if (rating === "A") state.treasuryEntries.push({ ...entryTemplate, id: "entry-A", incomingReceiptId: receiptId, amount: "25000" });
    });
    return state;
  }

  it("classifica corretamente as faixas A até HH", () => {
    const state = stateWithAllRatings();
    for (const rating of ["A", "B", "C", "D", "E", "F", "G", "H", "HH"] as const) {
      expect(classifyPddRating(state, state.fundingContracts.find((item) => item.id === `contract-${rating}`)!, "2026-08-07")).toBe(rating);
    }
  });

  it("fecha totais, clientes, contratos, principal, recebido, pendente e participações por rating", () => {
    const report = buildPddReport(stateWithAllRatings(), { asOf: "2026-08-07" });
    expect(report.rows.map((item) => item.rating)).toEqual(["A", "B", "C", "D", "E", "F", "G", "H", "HH"]);
    expect(report.rows.every((item) => item.clientCount === 1 && item.contractCount === 1)).toBe(true);
    expect(report.totals).toMatchObject({ clientCount: 9, contractCount: 9, principal: "9000000", received: "25000", pending: "8975000" });
    expect(report.rows.reduce((total, item) => total + item.clientShareBps, 0)).toBe(10_000);
    expect(report.rows.reduce((total, item) => total + item.contractShareBps, 0)).toBe(10_000);
    expect(report.rows.reduce((total, item) => total + item.principalShareBps, 0)).toBe(10_000);
    expect(report.rows.reduce((total, item) => total + item.receivedShareBps, 0)).toBe(10_000);
    expect(report.rows.reduce((total, item) => total + item.pendingShareBps, 0)).toBe(10_000);
    expect(sumCents(report.rows.map((item) => item.principal))).toBe(report.totals.principal);
    expect(sumCents(report.rows.map((item) => item.received))).toBe(report.totals.received);
    expect(sumCents(report.rows.map((item) => item.pending))).toBe(report.totals.pending);
  });

  it("não trata nenhuma fórmula fictícia de PDD como definitiva", () => {
    const report = buildPddReport(stateWithAllRatings());
    expect(report.totals.pddAmount).toBeUndefined();
    expect(report.rows.every((item) => item.pddAmount === undefined && item.pddShareBps === undefined && item.pddRuleStatus === "RULE_TO_CONFIRM")).toBe(true);
  });

  it("deriva fluxo mensal, empréstimos, principal, juros e remuneração sem duplicação", () => {
    const report = buildInvestorCashFlowReport(cloneDemoState(), "inv-demo-001");
    const july = report.rows.find((item) => item.competence === "2026-07")!;
    expect(report).toMatchObject({ originalContribution: "10000000", additionalContributions: "5000000", principalReceived: "466667", interestReceived: "133333", paidRemuneration: "190000" });
    expect(july).toMatchObject({ allocations: "6000000", principalReceived: "466667", interestReceived: "133333", remuneration: "190000", reinvestments: "70000", rocRuleStatus: "RULE_TO_CONFIRM" });
    expect(july.roc).toBeUndefined();
    expect(new Set(report.rows.flatMap((item) => item.detail.fundedContracts.map((event) => event.id))).size).toBe(report.rows.flatMap((item) => item.detail.fundedContracts).length);
    expect(report.contributionIds).toEqual(["apt-demo-001", "apt-demo-002"]);
    expect(report.contractIds).toEqual(["sale-demo-001"]);
    expect("bankAccount" in report).toBe(false);
  });

  it("calcula saldo histórico por competência e percentual utilizado", () => {
    const report = buildInvestorCashFlowReport(cloneDemoState(), "inv-demo-001"); const january = report.rows.find((item) => item.competence === "2026-01")!; const april = report.rows.find((item) => item.competence === "2026-04")!; const july = report.rows.find((item) => item.competence === "2026-07")!;
    expect(january).toMatchObject({ openingBalance: "0", contributions: "10000000", closingBalance: "10000000" });
    expect(april).toMatchObject({ openingBalance: "10000000", contributions: "5000000", closingBalance: "15000000" });
    expect(july.closingBalance).toBe("9536667");
    expect(report.currentUtilizationBps).toBe(ratioBps(report.allocatedCapital, report.currentCapital));
  });

  it("filtra aporte específico e preserva múltiplos aportes na visão consolidada", () => {
    const all = buildInvestorCashFlowReport(cloneDemoState(), "inv-demo-001"); const second = buildInvestorCashFlowReport(cloneDemoState(), "inv-demo-001", { contributionId: "apt-demo-002" });
    expect(all.contributionIds).toEqual(["apt-demo-001", "apt-demo-002"]);
    expect(second).toMatchObject({ contributionIds: ["apt-demo-002"], originalContribution: "5000000", additionalContributions: "0" });
    expect(second.rows.find((item) => item.competence === "2026-07")?.reinvestments).toBe("70000");
  });

  it("seleciona período sem perder o saldo histórico de abertura", () => {
    const report = buildInvestorCashFlowReport(cloneDemoState(), "inv-demo-001", { preset: "last6", asOf: "2026-08-07" });
    expect(report.rows.map((item) => item.competence)).toEqual(["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]);
    expect(report.rows[0].openingBalance).toBe("10000000");
  });

  it("mantém operações monetárias do FC em bigint para valores grandes", () => {
    const state = cloneDemoState(); state.contributions[0].originalAmount = "90071992547409931234567890";
    const report = buildInvestorCashFlowReport(state, "inv-demo-001", { contributionId: "apt-demo-001" });
    expect(report.originalContribution).toBe("90071992547409931234567890");
    expect(report.rows.find((item) => item.competence === "2026-01")?.closingBalance).toBe("90071992547409931234567890");
  });
});

describe("integridade monetária e referencial", () => {
  it("faz somas e médias ponderadas sem float monetário", () => {
    expect(sumCents(["90071992547409931234567890", "10"])).toBe("90071992547409931234567900");
    expect(weightedAverageBps([{ weight: "100", rateBps: 100 }, { weight: "300", rateBps: 300 }])).toBe(250);
  });

  it("não duplica entidades de origem entre grupos de um mesmo relatório", () => {
    const state = cloneDemoState();
    const harvestIds = buildHarvestReport(state).flatMap((item) => item.sourceContractIds);
    const receiptIds = buildRevenueReport(state).flatMap((item) => item.sourceReceiptIds);
    expect(new Set(harvestIds).size).toBe(harvestIds.length);
    expect(new Set(receiptIds).size).toBe(receiptIds.length);
  });
});
