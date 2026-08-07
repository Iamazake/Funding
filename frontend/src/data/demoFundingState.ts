import type { FundingState } from "@/types/funding";

export const DEMO_STATE: FundingState = {
  version: 4,
  investors: [
    {
      id: "inv-demo-001", code: "INV-DEMO-0001", name: "Aurora Capital Demonstrativa", personType: "PJ",
      maskedDocument: "22.***.***/****-22", riskGrade: "BAIXO", contractSigned: true,
      signedAt: "2026-01-12", paymentDay: 10, status: "ATIVO",
      contacts: [{ label: "E-mail", value: "capital@aurora.demo" }, { label: "Telefone", value: "(00) 90000-1001" }],
      bankAccount: { bank: "Banco Fictício Azul", branchMasked: "****", accountMasked: "*****-**", pixMasked: "a***@demo.invalid" },
      notes: "Cadastro integralmente fictício.", createdAt: "2026-01-12T12:00:00.000Z", updatedAt: "2026-04-05T12:00:00.000Z",
    },
    {
      id: "inv-demo-002", code: "INV-DEMO-0002", name: "Pessoa Investidora Exemplo", personType: "PF",
      maskedDocument: "222.***.***-22", riskGrade: "MEDIO", contractSigned: true,
      signedAt: "2026-02-22", paymentDay: 15, status: "ATIVO",
      contacts: [{ label: "E-mail", value: "investidor@exemplo.demo" }, { label: "Telefone", value: "(00) 90000-1002" }],
      bankAccount: { bank: "Instituição Demo Verde", branchMasked: "****", accountMasked: "*****-**", pixMasked: "***.***.***-**" },
      notes: "Cadastro fictício.", createdAt: "2026-02-22T12:00:00.000Z", updatedAt: "2026-02-22T12:00:00.000Z",
    },
    {
      id: "inv-demo-003", code: "INV-DEMO-0003", name: "Vértice Participações Demo", personType: "PJ",
      maskedDocument: "33.***.***/****-33", riskGrade: "ALTO", contractSigned: false,
      signedAt: null, paymentDay: 20, status: "PENDENTE", contacts: [{ label: "E-mail", value: "vertice@empresa.demo" }],
      bankAccount: { bank: "Banco Cenário", branchMasked: "****", accountMasked: "*****-**", pixMasked: "v***@demo.invalid" },
      notes: "Contrato demonstrativo pendente.", createdAt: "2026-04-02T12:00:00.000Z", updatedAt: "2026-04-02T12:00:00.000Z",
    },
  ],
  contributions: [
    {
      id: "apt-demo-001", investorId: "inv-demo-001", code: "APT-DEMO-0001",
      originalAmount: "10000000", availableBalance: "4000000", allocatedBalance: "6000000",
      startDate: "2026-01-12", endDate: "2027-01-12", monthlyRateBps: 200,
      expectedMonthlyRemuneration: "200000", status: "PARCIALMENTE_ALOCADO", notes: "Base: valor originalmente aportado.",
      createdAt: "2026-01-12T12:00:00.000Z", updatedAt: "2026-07-04T12:00:00.000Z",
    },
    {
      id: "apt-demo-002", investorId: "inv-demo-001", code: "APT-DEMO-0002",
      originalAmount: "5000000", availableBalance: "2500000", allocatedBalance: "2500000",
      startDate: "2026-04-05", endDate: "2027-04-05", monthlyRateBps: 150,
      expectedMonthlyRemuneration: "75000", status: "PARCIALMENTE_ALOCADO", notes: "Segundo aporte simultâneo demonstrativo.",
      createdAt: "2026-04-05T12:00:00.000Z", updatedAt: "2026-07-10T12:00:00.000Z",
    },
    {
      id: "apt-demo-003", investorId: "inv-demo-002", code: "APT-DEMO-0003",
      originalAmount: "8000000", availableBalance: "3000000", allocatedBalance: "5000000",
      startDate: "2026-02-22", endDate: "2027-02-22", monthlyRateBps: 175,
      expectedMonthlyRemuneration: "140000", status: "PARCIALMENTE_ALOCADO", notes: "Aporte fictício.",
      createdAt: "2026-02-22T12:00:00.000Z", updatedAt: "2026-07-12T12:00:00.000Z",
    },
  ],
  capitalRemunerationEvents: [
    {
      id: "rem-demo-001", investorId: "inv-demo-001", contributionId: "apt-demo-001", competence: "2026-07",
      originalContributionAmount: "10000000", monthlyRateBps: 200, calculationBase: "ORIGINAL_CONTRIBUTION_AMOUNT",
      grossAmount: "200000", informedPjrAmount: "10000", netAmount: "190000", expectedDate: "2026-07-10",
      paymentDate: "2026-07-10", status: "PAGA", settlementMethod: "BANK_TRANSFER", cashAccount: "Conta Caixa Demo 01",
      notes: "Pagamento fictício confirmado.", history: [{ id: "remh-001", action: "PAGAMENTO", description: "Pagamento demonstrativo confirmado.", date: "2026-07-10T12:00:00.000Z", responsibleUser: "Tesouraria Demo" }],
    },
    {
      id: "rem-demo-002", investorId: "inv-demo-001", contributionId: "apt-demo-002", competence: "2026-07",
      originalContributionAmount: "5000000", monthlyRateBps: 150, calculationBase: "ORIGINAL_CONTRIBUTION_AMOUNT",
      grossAmount: "75000", informedPjrAmount: "5000", netAmount: "70000", expectedDate: "2026-07-10",
      paymentDate: "2026-07-10", status: "REINVESTIDA", settlementMethod: "REINVESTMENT",
      notes: "Reinvestimento demonstrativo.", history: [{ id: "remh-002", action: "REINVESTIMENTO", description: "Reinvestimento sem saída bancária.", date: "2026-07-10T12:00:00.000Z", responsibleUser: "Tesouraria Demo" }],
    },
    {
      id: "rem-demo-003", investorId: "inv-demo-002", contributionId: "apt-demo-003", competence: "2026-08",
      originalContributionAmount: "8000000", monthlyRateBps: 175, calculationBase: "ORIGINAL_CONTRIBUTION_AMOUNT",
      grossAmount: "140000", informedPjrAmount: "8000", netAmount: "132000", expectedDate: "2026-08-15",
      status: "A_VENCER", settlementMethod: "NOT_DEFINED", notes: "Previsão demonstrativa.", history: [],
    },
  ],
  fundingSources: [
    { id: "src-apt-001", type: "INVESTOR_CONTRIBUTION", name: "APT-DEMO-0001", reference: "apt-demo-001", historicalAvailableAmount: "10000000", status: "ACTIVE" },
    { id: "src-apt-002", type: "INVESTOR_CONTRIBUTION", name: "APT-DEMO-0002", reference: "apt-demo-002", historicalAvailableAmount: "5000000", status: "ACTIVE" },
    { id: "src-apt-003", type: "INVESTOR_CONTRIBUTION", name: "APT-DEMO-0003", reference: "apt-demo-003", historicalAvailableAmount: "8000000", status: "ACTIVE" },
    { id: "src-remo", type: "REMO_OWN_CAPITAL", name: "Capital próprio REMO", historicalAvailableAmount: "25000000", status: "ACTIVE" },
    { id: "src-other", type: "OTHER_SOURCE", name: "Linha parceira demonstrativa", reference: "FONTE-DEMO-01", historicalAvailableAmount: "7000000", status: "ACTIVE" },
    { id: "src-unidentified", type: "UNIDENTIFIED_SOURCE", name: "Fonte pendente de identificação", historicalAvailableAmount: "0", status: "PENDING_IDENTIFICATION" },
  ],
  fundingLedgerEntries: [
    { id: "led-001", fundingSourceId: "src-apt-001", contributionId: "apt-demo-001", type: "ENTRY", amount: "10000000", date: "2026-01-12", reference: "APT-DEMO-0001" },
    { id: "led-002", fundingSourceId: "src-apt-002", contributionId: "apt-demo-002", type: "ENTRY", amount: "5000000", date: "2026-04-05", reference: "APT-DEMO-0002" },
    { id: "led-003", fundingSourceId: "src-apt-003", contributionId: "apt-demo-003", type: "ENTRY", amount: "8000000", date: "2026-02-22", reference: "APT-DEMO-0003" },
    { id: "led-004", fundingSourceId: "src-remo", type: "ENTRY", amount: "25000000", date: "2026-01-01", reference: "CAPITAL-REMO-DEMO" },
    { id: "led-005", fundingSourceId: "src-other", type: "ENTRY", amount: "7000000", date: "2026-03-01", reference: "FONTE-DEMO-01" },
  ],
  fundingContracts: [
    {
      id: "sale-demo-001", contractCode: "CTR-DEMO-1001", maskedClientName: "Cliente A*** Demonstrativo",
      operationDate: "2026-07-04", releaseDate: "2026-07-04", principalAmount: "9000000", financedAmount: "9500000",
      releasedAmount: "9000000", installmentAmount: "950000", projectedAmount: "11400000", releaseReference: "BANK-OUT-DEMO-001",
      cashOperator: "Conferente Demo", releaseBankAccount: "Conta Caixa Demo 01", releaseValidationStatus: "VALID",
      releaseValidationDate: "2026-07-05", termMonths: 12, interestRateBps: 245,
      status: "RELEASED", fundingValidationStatus: "VALID",
      responsibleUser: "Operador Demo", notes: "Contrato fictício com funding completo.", createdAt: "2026-07-04T12:00:00.000Z", updatedAt: "2026-07-05T12:00:00.000Z",
    },
    {
      id: "sale-demo-002", contractCode: "CTR-DEMO-1002", maskedClientName: "Cliente B*** Demonstrativo",
      operationDate: "2026-07-12", releaseDate: "2026-07-12", principalAmount: "8000000", financedAmount: "8400000",
      releasedAmount: "8000000", installmentAmount: "700000", projectedAmount: "9800000", releaseReference: "BANK-OUT-DEMO-002",
      cashOperator: "Operador Demo", releaseBankAccount: "Conta Caixa Demo 02", releaseValidationStatus: "DIVERGENT",
      releaseValidationDate: "2026-07-13", termMonths: 14, interestRateBps: 265,
      status: "FUNDING_DIVERGENT", fundingValidationStatus: "DIVERGENT",
      responsibleUser: "Operador Demo", notes: "Contrato preservado com diferença de funding para correção posterior.", createdAt: "2026-07-12T12:00:00.000Z", updatedAt: "2026-07-12T12:00:00.000Z",
    },
  ],
  contractFundingAllocations: [
    { id: "alloc-001", fundingContractId: "sale-demo-001", fundingSourceType: "INVESTOR_CONTRIBUTION", contributionId: "apt-demo-001", investorId: "inv-demo-001", fundingSourceId: "src-apt-001", amount: "6000000", allocationDate: "2026-07-04", validFrom: "2026-07-04", historicalAvailableBalance: "10000000", validationStatus: "VALID", notes: "Alocação demonstrativa." },
    { id: "alloc-002", fundingContractId: "sale-demo-001", fundingSourceType: "REMO_OWN_CAPITAL", fundingSourceId: "src-remo", amount: "3000000", allocationDate: "2026-07-04", validFrom: "2026-07-04", historicalAvailableBalance: "25000000", validationStatus: "VALID", notes: "Capital próprio, sem investidor fictício." },
    { id: "alloc-003", fundingContractId: "sale-demo-002", fundingSourceType: "INVESTOR_CONTRIBUTION", contributionId: "apt-demo-003", investorId: "inv-demo-002", fundingSourceId: "src-apt-003", amount: "5000000", allocationDate: "2026-07-12", validFrom: "2026-07-12", historicalAvailableBalance: "8000000", validationStatus: "VALID", notes: "Alocação demonstrativa." },
    { id: "alloc-004", fundingContractId: "sale-demo-002", fundingSourceType: "UNIDENTIFIED_SOURCE", fundingSourceId: "src-unidentified", amount: "1000000", allocationDate: "2026-07-12", validFrom: "2026-07-12", historicalAvailableBalance: "0", validationStatus: "DIVERGENT", divergenceReason: "Fonte ainda não identificada.", notes: "Correção pendente." },
  ],
  fundingDivergences: [
    { id: "divg-001", fundingContractId: "sale-demo-002", type: "FUNDING_TOTAL_MISMATCH", expectedAmount: "8000000", identifiedAmount: "6000000", differenceAmount: "2000000", description: "Funding informado menor que o valor liberado.", status: "OPEN", createdAt: "2026-07-12T12:00:00.000Z" },
    { id: "divg-002", fundingContractId: "sale-demo-002", type: "UNIDENTIFIED_FUNDING_SOURCE", expectedAmount: "1000000", identifiedAmount: "0", differenceAmount: "1000000", description: "Há fonte pendente de identificação.", status: "OPEN", createdAt: "2026-07-12T12:00:00.000Z" },
  ],
  treasuryIncomingReceipts: [
    { id: "receipt-001", fundingContractId: "sale-demo-001", contractCode: "CTR-DEMO-1001", maskedClientName: "Cliente A*** Demonstrativo", installmentNumber: 1, totalInstallments: 12, dueDate: "2026-07-30", operationalWriteOffDate: "2026-07-30", expectedAmount: "950000", paidAmountFromOperationalSource: "950000", principalAmount: "700000", interestAmount: "200000", iofAmount: "50000", penaltyAmount: "0", discountAmount: "0", lossAmount: "0", operationalStatus: "WRITTEN_OFF", bankValidationStatus: "VALIDATED", reconciliationStatus: "RECONCILED", status: "VALIDATED", sourceReference: "ECON-AMTZ-DEMO-001", responsibleUser: "Tesouraria Demo", notes: "Baixa operacional e conferência bancária fictícias.", createdAt: "2026-07-30T11:00:00.000Z", updatedAt: "2026-07-30T12:00:00.000Z" },
    { id: "receipt-002", fundingContractId: "sale-demo-002", contractCode: "CTR-DEMO-1002", maskedClientName: "Cliente B*** Demonstrativo", installmentNumber: 1, totalInstallments: 14, dueDate: "2026-08-12", operationalWriteOffDate: "2026-08-01", expectedAmount: "700000", paidAmountFromOperationalSource: "700000", principalAmount: "500000", interestAmount: "180000", iofAmount: "20000", penaltyAmount: "0", discountAmount: "0", lossAmount: "0", operationalStatus: "WRITTEN_OFF", bankValidationStatus: "VALUE_MISMATCH", reconciliationStatus: "PARTIAL", status: "PARTIALLY_VALIDATED", sourceReference: "ECON-AMTZ-DEMO-002", responsibleUser: "Tesouraria Demo", notes: "Pagamento parcial fictício para fila de trabalho.", createdAt: "2026-08-01T12:00:00.000Z", updatedAt: "2026-08-02T12:00:00.000Z" },
    { id: "receipt-003", fundingContractId: "sale-demo-001", contractCode: "CTR-DEMO-1001", maskedClientName: "Cliente A*** Demonstrativo", installmentNumber: 2, totalInstallments: 12, dueDate: "2026-08-30", operationalWriteOffDate: "2026-08-02", expectedAmount: "950000", paidAmountFromOperationalSource: "900000", principalAmount: "650000", interestAmount: "200000", iofAmount: "30000", penaltyAmount: "10000", discountAmount: "0", lossAmount: "0", operationalStatus: "WRITTEN_OFF", bankValidationStatus: "PENDING", reconciliationStatus: "PENDING", status: "WAITING_BANK_VALIDATION", sourceReference: "ECON-AMTZ-DEMO-003", responsibleUser: "Operador Financeiro Demo", notes: "Componentes fictícios somam R$ 8.900,00 para pagamento de R$ 9.000,00.", createdAt: "2026-08-02T12:00:00.000Z", updatedAt: "2026-08-02T12:00:00.000Z" },
    { id: "receipt-004", fundingContractId: "sale-demo-001", contractCode: "CTR-DEMO-1001", maskedClientName: "Cliente A*** Demonstrativo", installmentNumber: 3, totalInstallments: 12, dueDate: "2026-09-30", operationalWriteOffDate: "2026-08-03", expectedAmount: "950000", paidAmountFromOperationalSource: "950000", principalAmount: "700000", interestAmount: "250000", iofAmount: "50000", penaltyAmount: "20000", discountAmount: "40000", lossAmount: "30000", operationalStatus: "WRITTEN_OFF", bankValidationStatus: "MOVEMENT_NOT_FOUND", reconciliationStatus: "DIVERGENT", status: "BANK_MOVEMENT_NOT_FOUND", sourceReference: "ECON-AMTZ-DEMO-004", responsibleUser: "Operador Financeiro Demo", notes: "Tentativa fictícia sem movimento localizado.", createdAt: "2026-08-03T12:00:00.000Z", updatedAt: "2026-08-03T13:00:00.000Z" },
  ],
  bankMovements: [
    { id: "bank-001", bankAccountId: "Conta Caixa Demo 01", movementDate: "2026-07-30", amount: "950000", transactionReference: "BANK-DEMO-001", payerDescription: "Pagador A***", checkedBy: "Conferente Demo", checkedAt: "2026-07-30T12:00:00.000Z", status: "FOUND", notes: "Movimento bancário fictício." },
    { id: "bank-002", bankAccountId: "Conta Caixa Demo 02", movementDate: "2026-08-02", amount: "300000", transactionReference: "BANK-DEMO-002", payerDescription: "Pagador B***", checkedBy: "Conferente Demo", checkedAt: "2026-08-02T12:00:00.000Z", status: "FOUND", notes: "Parte do recebimento localizada." },
    { id: "bank-003", bankAccountId: "Conta Caixa Demo 01", movementDate: "2026-08-03", amount: "0", transactionReference: "BUSCA-DEMO-003", payerDescription: "Pagador não localizado", checkedBy: "Conferente Demo", checkedAt: "2026-08-03T13:00:00.000Z", status: "NOT_FOUND", notes: "Tentativa de conferência fictícia." },
  ],
  receiptBankReconciliations: [
    { id: "link-001", incomingReceiptId: "receipt-001", bankMovementId: "bank-001", amount: "950000", status: "ACTIVE", confirmedBy: "Conferente Demo", confirmedAt: "2026-07-30T12:00:00.000Z", notes: "Conciliação demonstrativa." },
    { id: "link-002", incomingReceiptId: "receipt-002", bankMovementId: "bank-002", amount: "300000", status: "ACTIVE", confirmedBy: "Conferente Demo", confirmedAt: "2026-08-02T12:00:00.000Z", notes: "Pagamento parcial demonstrativo." },
    { id: "link-003", incomingReceiptId: "receipt-004", bankMovementId: "bank-003", amount: "0", status: "ACTIVE", confirmedBy: "Conferente Demo", confirmedAt: "2026-08-03T13:00:00.000Z", notes: "Tentativa sem movimento encontrado." },
  ],
  treasuryDivergences: [
    { id: "tdiv-001", incomingReceiptId: "receipt-002", type: "BANK_AMOUNT_MISMATCH", expectedAmount: "700000", reconciledAmount: "300000", differenceAmount: "400000", description: "Pagamento parcialmente localizado.", status: "OPEN", createdAt: "2026-08-02T12:00:00.000Z" },
    { id: "tdiv-002", incomingReceiptId: "receipt-004", type: "BANK_MOVEMENT_NOT_FOUND", expectedAmount: "950000", reconciledAmount: "0", differenceAmount: "950000", description: "Movimento não encontrado.", status: "OPEN", createdAt: "2026-08-03T13:00:00.000Z" },
  ],
  revenueDivergences: [
    { id: "revdiv-001", incomingReceiptId: "receipt-002", type: "PARTIAL_PAYMENT", expectedAmount: "700000", actualAmount: "300000", differenceAmount: "400000", description: "Recebimento bancário parcial.", status: "OPEN", createdAt: "2026-08-02T12:00:00.000Z", updatedAt: "2026-08-02T12:00:00.000Z" },
    { id: "revdiv-002", incomingReceiptId: "receipt-002", type: "BANK_AMOUNT_MISMATCH", expectedAmount: "700000", actualAmount: "300000", differenceAmount: "400000", description: "Valor bancário divergente.", status: "OPEN", sourceTreasuryDivergenceId: "tdiv-001", createdAt: "2026-08-02T12:00:00.000Z", updatedAt: "2026-08-02T12:00:00.000Z" },
    { id: "revdiv-003", incomingReceiptId: "receipt-003", type: "RECEIPT_COMPONENT_MISMATCH", expectedAmount: "900000", actualAmount: "890000", differenceAmount: "10000", description: "Componentes operacionais não fecham o valor pago.", status: "OPEN", createdAt: "2026-08-02T12:00:00.000Z", updatedAt: "2026-08-02T12:00:00.000Z" },
    { id: "revdiv-004", incomingReceiptId: "receipt-004", type: "BANK_MOVEMENT_NOT_FOUND", expectedAmount: "950000", actualAmount: "0", differenceAmount: "950000", description: "Movimento bancário não localizado.", status: "OPEN", sourceTreasuryDivergenceId: "tdiv-002", createdAt: "2026-08-03T13:00:00.000Z", updatedAt: "2026-08-03T13:00:00.000Z" },
  ],
  revenueColumnPreferences: {
    visibleColumns: ["contract", "installment", "dueDate", "paymentDate", "expected", "paid", "status", "operator", "principal", "interest", "iof", "loss", "discount", "apurated", "componentDifference", "paymentReference", "funding", "bankAccount", "bankDifference", "bankValidation", "revenueStatus"],
    density: "COMFORTABLE",
  },
  allocationReceiptShares: [
    { id: "share-001", incomingReceiptId: "receipt-001", contractFundingAllocationId: "alloc-001", fundingSourceType: "INVESTOR_CONTRIBUTION", investorId: "inv-demo-001", contributionId: "apt-demo-001", allocationBps: 6666, principalShare: "466667", interestShare: "133333", iofShare: "0", penaltyShare: "0", discountShare: "0", lossShare: "0", iofDestinationStatus: "RULE_TO_CONFIRM", status: "CONFIRMED", calculatedAt: "2026-07-30T12:00:00.000Z" },
    { id: "share-002", incomingReceiptId: "receipt-001", contractFundingAllocationId: "alloc-002", fundingSourceType: "REMO_OWN_CAPITAL", allocationBps: 3333, principalShare: "233333", interestShare: "66667", iofShare: "0", penaltyShare: "0", discountShare: "0", lossShare: "0", iofDestinationStatus: "RULE_TO_CONFIRM", status: "CONFIRMED", calculatedAt: "2026-07-30T12:00:00.000Z" },
  ],
  treasuryEntries: [
    { id: "mov-001", investorId: "inv-demo-001", contributionId: "apt-demo-001", type: "INVESTOR_CONTRIBUTION_RECEIVED", direction: "ENTRADA", amount: "10000000", date: "2026-01-12", competence: "2026-01", cashAccount: "Conta Caixa Demo 01", status: "CONFIRMADO", owner: "Tesouraria Demo", reference: "APT-DEMO-0001", notes: "Entrada fictícia.", createdAt: "2026-01-12T12:00:00.000Z" },
    { id: "mov-002", fundingContractId: "sale-demo-001", type: "CAPITAL_ALLOCATED", direction: "TRANSFERENCIA_INTERNA", amount: "9000000", date: "2026-07-04", competence: "2026-07", cashAccount: "Reserva contábil", status: "CONFIRMADO", owner: "Operador Demo", reference: "CTR-DEMO-1001", notes: "Reserva contábil; não é entrada nem saída bancária.", createdAt: "2026-07-04T12:00:00.000Z" },
    { id: "mov-003", fundingContractId: "sale-demo-001", type: "LOAN_RELEASE", direction: "SAIDA", amount: "9000000", date: "2026-07-04", competence: "2026-07", cashAccount: "Conta Caixa Demo 01", status: "CONFIRMADO", owner: "Conferente Demo", reference: "BANK-DEMO-001", notes: "Liberação do empréstimo registrada exclusivamente como saída.", createdAt: "2026-07-05T12:00:00.000Z" },
    { id: "mov-004", capitalRemunerationEventId: "rem-demo-001", investorId: "inv-demo-001", contributionId: "apt-demo-001", type: "CAPITAL_REMUNERATION_PAID", direction: "SAIDA", amount: "190000", date: "2026-07-10", competence: "2026-07", cashAccount: "Conta Caixa Demo 01", status: "CONFIRMADO", owner: "Tesouraria Demo", reference: "REM-DEMO-001", notes: "Pagamento demonstrativo.", createdAt: "2026-07-10T12:00:00.000Z" },
    { id: "mov-005", capitalRemunerationEventId: "rem-demo-002", investorId: "inv-demo-001", contributionId: "apt-demo-002", type: "REMUNERATION_REINVESTED", direction: "TRANSFERENCIA_INTERNA", amount: "70000", date: "2026-07-10", competence: "2026-07", cashAccount: "Conta Virtual de Reinvestimento", status: "CONFIRMADO", owner: "Tesouraria Demo", reference: "REINV-DEMO-001", notes: "Sem saída bancária.", createdAt: "2026-07-10T12:00:00.000Z" },
    { id: "mov-006", incomingReceiptId: "receipt-001", bankMovementId: "bank-001", type: "PMT_RECEIVED", direction: "ENTRADA", amount: "950000", date: "2026-07-30", competence: "2026-07", cashAccount: "Conta Caixa Demo 01", status: "CONFIRMADO", owner: "Tesouraria Demo", reference: "BANK-DEMO-001", notes: "Uma única entrada de caixa para a PMT completa; componentes não duplicam o caixa.", createdAt: "2026-07-30T12:00:00.000Z" },
    { id: "mov-007", incomingReceiptId: "receipt-002", bankMovementId: "bank-002", type: "PMT_RECEIVED", direction: "ENTRADA", amount: "300000", date: "2026-08-02", competence: "2026-08", cashAccount: "Conta Caixa Demo 02", status: "CONFIRMADO", owner: "Tesouraria Demo", reference: "BANK-DEMO-002", notes: "Entrada parcial única; componentes não duplicam caixa.", createdAt: "2026-08-02T12:00:00.000Z" },
  ],
  auditEvents: [
    { id: "aud-001", entity: "SYSTEM", entityId: "demo", action: "DADOS_INICIAIS", description: "Conjunto v4 de dados fictícios inicializado.", date: "2026-07-31T12:00:00.000Z", demoUser: "Usuário Demonstrativo" },
    { id: "aud-002", entity: "CONTRACT", entityId: "sale-demo-002", action: "FUNDING_INSUFICIENTE", description: "Contrato preservado com divergências de funding abertas.", date: "2026-07-12T12:00:00.000Z", demoUser: "Operador Demo" },
  ],
  reconciliations: [
    { id: "rec-001", cashAccount: "Conta Caixa Demo 01", calculatedBalance: "1760000", informedBalance: "1760000", difference: "0", status: "CONCILIADO", date: "2026-07-30", owner: "Tesouraria Demo", notes: "Conciliação fictícia." },
  ],
};

export function cloneDemoState(): FundingState {
  return structuredClone(DEMO_STATE);
}
