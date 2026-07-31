import type {
  Allocation,
  Contribution,
  FundingDashboardData,
  Investor,
  InvestorRemuneration,
  OperationalContract,
  ReportSnapshot,
  TreasuryMovement,
  TreasurySummary,
} from "@/types/funding";

export const mockInvestors: Investor[] = [
  { id: "inv-demo-001", name: "Aurora Capital Demo", type: "company", status: "active", maskedDocument: "00.***.***/****-00", email: "contato@aurora.demo", joinedAt: "2026-01-12", contributedCapital: "1250000.00", availableBalance: "285000.00", allocatedBalance: "965000.00", accumulatedReturn: "78240.50", nextPaymentDate: "2026-08-10", nextPaymentAmount: "18650.00" },
  { id: "inv-demo-002", name: "Horizonte Fundo Exemplo", type: "fund", status: "active", maskedDocument: "11.***.***/****-11", email: "operacoes@horizonte.demo", joinedAt: "2026-02-03", contributedCapital: "980000.00", availableBalance: "210000.00", allocatedBalance: "770000.00", accumulatedReturn: "61580.00", nextPaymentDate: "2026-08-12", nextPaymentAmount: "14780.00" },
  { id: "inv-demo-003", name: "Investidor Alfa Demonstrativo", type: "individual", status: "active", maskedDocument: "000.***.***-00", email: "alfa@exemplo.demo", joinedAt: "2026-02-18", contributedCapital: "640000.00", availableBalance: "96000.00", allocatedBalance: "544000.00", accumulatedReturn: "39410.25", nextPaymentDate: "2026-08-15", nextPaymentAmount: "9210.00" },
  { id: "inv-demo-004", name: "Investidora Beta Demonstrativa", type: "individual", status: "pending", maskedDocument: "111.***.***-11", email: "beta@exemplo.demo", joinedAt: "2026-03-08", contributedCapital: "420000.00", availableBalance: "145000.00", allocatedBalance: "275000.00", accumulatedReturn: "18320.00", nextPaymentDate: "2026-08-18", nextPaymentAmount: "5250.00" },
  { id: "inv-demo-005", name: "Vértice Participações Demo", type: "company", status: "active", maskedDocument: "22.***.***/****-22", email: "funding@vertice.demo", joinedAt: "2026-03-21", contributedCapital: "760000.00", availableBalance: "132000.00", allocatedBalance: "628000.00", accumulatedReturn: "42790.90", nextPaymentDate: "2026-08-20", nextPaymentAmount: "10890.00" },
  { id: "inv-demo-006", name: "Investidor Gama Demonstrativo", type: "individual", status: "inactive", maskedDocument: "222.***.***-22", email: "gama@exemplo.demo", joinedAt: "2026-04-02", contributedCapital: "310000.00", availableBalance: "0.00", allocatedBalance: "310000.00", accumulatedReturn: "15490.00", nextPaymentDate: null, nextPaymentAmount: "0.00" },
];

export const mockContributions: Contribution[] = [
  { id: "apt-demo-001", code: "APT-DEMO-0001", investorId: "inv-demo-001", investorName: "Aurora Capital Demo", status: "partially_allocated", originalAmount: "750000.00", availableAmount: "185000.00", allocatedAmount: "565000.00", monthlyRate: "1.45", startDate: "2026-01-12", endDate: "2027-01-12" },
  { id: "apt-demo-002", code: "APT-DEMO-0002", investorId: "inv-demo-001", investorName: "Aurora Capital Demo", status: "partially_allocated", originalAmount: "500000.00", availableAmount: "100000.00", allocatedAmount: "400000.00", monthlyRate: "1.40", startDate: "2026-04-05", endDate: "2027-04-05" },
  { id: "apt-demo-003", code: "APT-DEMO-0003", investorId: "inv-demo-002", investorName: "Horizonte Fundo Exemplo", status: "partially_allocated", originalAmount: "980000.00", availableAmount: "210000.00", allocatedAmount: "770000.00", monthlyRate: "1.35", startDate: "2026-02-03", endDate: "2027-02-03" },
  { id: "apt-demo-004", code: "APT-DEMO-0004", investorId: "inv-demo-003", investorName: "Investidor Alfa Demonstrativo", status: "partially_allocated", originalAmount: "640000.00", availableAmount: "96000.00", allocatedAmount: "544000.00", monthlyRate: "1.50", startDate: "2026-02-18", endDate: "2027-02-18" },
  { id: "apt-demo-005", code: "APT-DEMO-0005", investorId: "inv-demo-004", investorName: "Investidora Beta Demonstrativa", status: "partially_allocated", originalAmount: "420000.00", availableAmount: "145000.00", allocatedAmount: "275000.00", monthlyRate: "1.48", startDate: "2026-03-08", endDate: "2027-03-08" },
  { id: "apt-demo-006", code: "APT-DEMO-0006", investorId: "inv-demo-005", investorName: "Vértice Participações Demo", status: "partially_allocated", originalAmount: "760000.00", availableAmount: "132000.00", allocatedAmount: "628000.00", monthlyRate: "1.38", startDate: "2026-03-21", endDate: "2027-03-21" },
  { id: "apt-demo-007", code: "APT-DEMO-0007", investorId: "inv-demo-006", investorName: "Investidor Gama Demonstrativo", status: "allocated", originalAmount: "310000.00", availableAmount: "0.00", allocatedAmount: "310000.00", monthlyRate: "1.42", startDate: "2026-04-02", endDate: "2027-04-02" },
];

export const mockContracts: OperationalContract[] = [
  { id: "ctr-demo-001", code: "CTR-DEMO-0001", maskedClientName: "Cliente Demo A***", releasedAmount: "185000.00", principalAmount: "172000.00", installmentAmount: "5980.50", termMonths: 42, monthlyRate: "2.15", status: "partial", operationDate: "2026-07-03", requiredFunding: "185000.00", allocatedFunding: "120000.00", fundedPercent: "64.86" },
  { id: "ctr-demo-002", code: "CTR-DEMO-0002", maskedClientName: "Cliente Demo B***", releasedAmount: "240000.00", principalAmount: "226000.00", installmentAmount: "7145.80", termMonths: 48, monthlyRate: "2.08", status: "available", operationDate: "2026-07-08", requiredFunding: "240000.00", allocatedFunding: "0.00", fundedPercent: "0.00" },
  { id: "ctr-demo-003", code: "CTR-DEMO-0003", maskedClientName: "Cliente Demo C***", releasedAmount: "138000.00", principalAmount: "129500.00", installmentAmount: "4890.20", termMonths: 36, monthlyRate: "2.22", status: "funded", operationDate: "2026-07-11", requiredFunding: "138000.00", allocatedFunding: "138000.00", fundedPercent: "100.00" },
  { id: "ctr-demo-004", code: "CTR-DEMO-0004", maskedClientName: "Cliente Demo D***", releasedAmount: "315000.00", principalAmount: "298000.00", installmentAmount: "8640.75", termMonths: 54, monthlyRate: "1.98", status: "partial", operationDate: "2026-07-17", requiredFunding: "315000.00", allocatedFunding: "220000.00", fundedPercent: "69.84" },
  { id: "ctr-demo-005", code: "CTR-DEMO-0005", maskedClientName: "Cliente Demo E***", releasedAmount: "96000.00", principalAmount: "91000.00", installmentAmount: "3370.40", termMonths: 36, monthlyRate: "2.28", status: "available", operationDate: "2026-07-22", requiredFunding: "96000.00", allocatedFunding: "0.00", fundedPercent: "0.00" },
  { id: "ctr-demo-006", code: "CTR-DEMO-0006", maskedClientName: "Cliente Demo F***", releasedAmount: "410000.00", principalAmount: "387000.00", installmentAmount: "10850.00", termMonths: 60, monthlyRate: "1.92", status: "partial", operationDate: "2026-07-28", requiredFunding: "410000.00", allocatedFunding: "305000.00", fundedPercent: "74.39" },
];

export const mockAllocations: Allocation[] = [
  { id: "rat-demo-001", investorId: "inv-demo-001", investorName: "Aurora Capital Demo", contributionId: "apt-demo-001", contractId: "ctr-demo-001", contractCode: "CTR-DEMO-0001", amount: "120000.00", allocatedAt: "2026-07-04", status: "active" },
  { id: "rat-demo-002", investorId: "inv-demo-002", investorName: "Horizonte Fundo Exemplo", contributionId: "apt-demo-003", contractId: "ctr-demo-003", contractCode: "CTR-DEMO-0003", amount: "138000.00", allocatedAt: "2026-07-12", status: "active" },
  { id: "rat-demo-003", investorId: "inv-demo-005", investorName: "Vértice Participações Demo", contributionId: "apt-demo-006", contractId: "ctr-demo-004", contractCode: "CTR-DEMO-0004", amount: "220000.00", allocatedAt: "2026-07-18", status: "active" },
];

export const mockRemunerations: InvestorRemuneration[] = [
  { id: "rem-demo-001", investorId: "inv-demo-001", reference: "Julho/2026", amount: "18650.00", dueDate: "2026-08-10", status: "scheduled" },
  { id: "rem-demo-002", investorId: "inv-demo-002", reference: "Julho/2026", amount: "14780.00", dueDate: "2026-08-12", status: "scheduled" },
  { id: "rem-demo-003", investorId: "inv-demo-003", reference: "Julho/2026", amount: "9210.00", dueDate: "2026-08-15", status: "scheduled" },
  { id: "rem-demo-004", investorId: "inv-demo-004", reference: "Julho/2026", amount: "5250.00", dueDate: "2026-08-18", status: "scheduled" },
  { id: "rem-demo-005", investorId: "inv-demo-005", reference: "Julho/2026", amount: "10890.00", dueDate: "2026-08-20", status: "scheduled" },
];

export const mockTreasuryMovements: TreasuryMovement[] = [
  { id: "mov-demo-001", type: "contribution", investorId: "inv-demo-001", investorName: "Aurora Capital Demo", date: "2026-07-02", amount: "500000.00", direction: "in", description: "Aporte demonstrativo recebido", status: "completed" },
  { id: "mov-demo-002", type: "allocation", investorId: "inv-demo-001", investorName: "Aurora Capital Demo", date: "2026-07-04", amount: "120000.00", direction: "out", description: "Alocação simulada no CTR-DEMO-0001", status: "completed" },
  { id: "mov-demo-003", type: "remuneration", investorId: "inv-demo-002", investorName: "Horizonte Fundo Exemplo", date: "2026-07-10", amount: "14200.00", direction: "out", description: "Remuneração demonstrativa", status: "completed" },
  { id: "mov-demo-004", type: "refund", investorId: "inv-demo-003", investorName: "Investidor Alfa Demonstrativo", date: "2026-07-15", amount: "32000.00", direction: "out", description: "Devolução parcial demonstrativa", status: "completed" },
  { id: "mov-demo-005", type: "reinvestment", investorId: "inv-demo-004", investorName: "Investidora Beta Demonstrativa", date: "2026-07-19", amount: "18500.00", direction: "in", description: "Reinvestimento demonstrativo", status: "completed" },
  { id: "mov-demo-006", type: "pjr", investorId: "inv-demo-005", investorName: "Vértice Participações Demo", date: "2026-07-23", amount: "7850.00", direction: "out", description: "PJR demonstrativo — regra a definir", status: "scheduled" },
  { id: "mov-demo-007", type: "allocation", investorId: "inv-demo-005", investorName: "Vértice Participações Demo", date: "2026-07-25", amount: "220000.00", direction: "out", description: "Alocação simulada no CTR-DEMO-0004", status: "completed" },
];

export const mockDashboard: FundingDashboardData = {
  metrics: [
    { id: "captured", label: "Total captado", value: "4360000.00", variationPercent: "8.4", direction: "up" },
    { id: "available", label: "Capital disponível", value: "868000.00", variationPercent: "3.1", direction: "up" },
    { id: "allocated", label: "Capital alocado", value: "3492000.00", variationPercent: "9.8", direction: "up" },
    { id: "portfolio", label: "Carteira ativa", value: "3928000.00", variationPercent: "6.2", direction: "up" },
    { id: "return", label: "Retorno acumulado", value: "255831.65", variationPercent: "7.5", direction: "up" },
    { id: "payments", label: "Pagamentos previstos", value: "58780.00", variationPercent: "1.7", direction: "down" },
  ],
  fundingEvolution: [
    { label: "Fev", value: 1850, secondaryValue: 1420 }, { label: "Mar", value: 2280, secondaryValue: 1760 },
    { label: "Abr", value: 2760, secondaryValue: 2180 }, { label: "Mai", value: 3210, secondaryValue: 2590 },
    { label: "Jun", value: 3890, secondaryValue: 3120 }, { label: "Jul", value: 4360, secondaryValue: 3492 },
  ],
  capitalPosition: [{ label: "Disponível", value: 868 }, { label: "Alocado", value: 3492 }],
  investorDistribution: [
    { label: "Aurora", value: 1250 }, { label: "Horizonte", value: 980 }, { label: "Alfa", value: 640 },
    { label: "Beta", value: 420 }, { label: "Vértice", value: 760 }, { label: "Gama", value: 310 },
  ],
  upcomingPayments: [
    { id: "pay-demo-001", investorName: "Aurora Capital Demo", dueDate: "2026-08-10", amount: "18650.00", kind: "remuneration" },
    { id: "pay-demo-002", investorName: "Horizonte Fundo Exemplo", dueDate: "2026-08-12", amount: "14780.00", kind: "remuneration" },
    { id: "pay-demo-003", investorName: "Investidor Alfa Demonstrativo", dueDate: "2026-08-15", amount: "9210.00", kind: "remuneration" },
  ],
  recentActivities: [
    { id: "act-demo-001", title: "Aporte demonstrativo registrado", description: "APT-DEMO-0007 foi disponibilizado no ambiente local.", occurredAt: "2026-07-30", tone: "success" },
    { id: "act-demo-002", title: "Rateio simulado", description: "CTR-DEMO-0004 recebeu uma alocação fictícia.", occurredAt: "2026-07-29", tone: "info" },
    { id: "act-demo-003", title: "Pagamento previsto", description: "Agenda demonstrativa de agosto foi atualizada.", occurredAt: "2026-07-28", tone: "warning" },
  ],
};

export const mockTreasury: TreasurySummary = {
  generalBalance: "868000.00", totalInflows: "4378500.00", totalOutflows: "3510500.00",
  totalRemuneration: "255831.65", totalRefunds: "124000.00", totalReinvestments: "78500.00", totalPjr: "31850.00",
  movements: mockTreasuryMovements,
};

export const mockReports: ReportSnapshot = {
  generatedAt: "2026-07-31",
  fundingByInvestor: mockDashboard.investorDistribution,
  returnByInvestor: [{ label: "Aurora", value: 78 }, { label: "Horizonte", value: 62 }, { label: "Alfa", value: 39 }, { label: "Beta", value: 18 }, { label: "Vértice", value: 43 }],
  capitalPosition: mockDashboard.capitalPosition,
  remunerationForecast: [{ label: "Ago", value: 59 }, { label: "Set", value: 63 }, { label: "Out", value: 67 }, { label: "Nov", value: 71 }, { label: "Dez", value: 74 }],
  treasuryByType: [{ label: "Entradas", value: 4378 }, { label: "Alocações", value: 3099 }, { label: "Remuneração", value: 256 }, { label: "Devoluções", value: 124 }, { label: "PJR", value: 32 }],
  contractDistribution: [{ label: "Financiados", value: 48 }, { label: "Parciais", value: 31 }, { label: "Disponíveis", value: 21 }],
};
