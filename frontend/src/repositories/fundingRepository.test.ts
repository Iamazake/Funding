import { describe, expect, it } from "vitest";

import { cloneDemoState } from "@/data/demoFundingState";
import { buildRevenueRecords, calculateApuratedAmount, calculateComponentDifference } from "@/lib/revenue";
import {
  calculateCapitalRemuneration, calculateHistoricalAvailableBalance, cents,
  FUNDING_STORAGE_KEY, FundingRepository, LEGACY_FUNDING_STORAGE_KEY,
  LEGACY_V2_STORAGE_KEY, LEGACY_V3_STORAGE_KEY, migrateFundingState, proportionalSplit, sumCents,
  type StorageAdapter,
} from "@/repositories/fundingRepository";
import type {
  BankMovementInput, ContractFundingAllocationInput, ContributionInput,
  FundingContractInput, TreasuryIncomingReceiptInput,
} from "@/types/funding";

class MemoryStorage implements StorageAdapter {
  readonly values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

function repository(storage = new MemoryStorage()) {
  let sequence = 0;
  return new FundingRepository(storage, {
    now: () => new Date("2026-07-31T15:00:00.000Z"),
    idFactory: () => `test-${++sequence}`,
  });
}

function contributionInput(investorId: string, amount: string): ContributionInput {
  return { investorId, originalAmount: amount, availableBalance: amount, allocatedBalance: "0", startDate: "2026-07-31", endDate: "2027-07-31", monthlyRateBps: 200, status: "ATIVO", notes: "Teste fictício." };
}

function contractInput(code: string, released = "1000000", operationDate = "2026-07-01"): FundingContractInput {
  return { contractCode: code, maskedClientName: "Cliente T*** Demonstrativo", operationDate, releaseDate: operationDate, principalAmount: released, financedAmount: released, releasedAmount: released, installmentAmount: "100000", termMonths: 12, interestRateBps: 250, responsibleUser: "Teste", notes: "Contrato fictício." };
}

function allocation(sourceId: string, type: ContractFundingAllocationInput["fundingSourceType"], amount: string, operationDate = "2026-07-01"): ContractFundingAllocationInput {
  return { fundingSourceType: type, fundingSourceId: sourceId, amount, allocationDate: operationDate, notes: "Teste." };
}

function incomingInput(contractId: string, code: string, expected = "100000", writeOffDate = "2026-07-15"): TreasuryIncomingReceiptInput {
  return { fundingContractId: contractId, contractCode: code, maskedClientName: "Cliente T*** Demonstrativo", installmentNumber: 1, totalInstallments: 12, dueDate: "2026-07-15", operationalWriteOffDate: writeOffDate, expectedAmount: expected, paidAmountFromOperationalSource: expected, principalAmount: (BigInt(expected) * 7n / 10n).toString(), interestAmount: (BigInt(expected) * 3n / 10n).toString(), iofAmount: "0", penaltyAmount: "0", discountAmount: "0", lossAmount: "0", operationalStatus: "WRITTEN_OFF", sourceReference: `SRC:${code}`, responsibleUser: "Teste", notes: "Baixa fictícia." };
}

function movement(amount: string, reference: string, status: BankMovementInput["status"] = "FOUND"): BankMovementInput {
  return { bankAccountId: "Conta Demo", movementDate: "2026-07-16", amount, transactionReference: reference, payerDescription: "Pagador T***", checkedBy: "Teste", checkedAt: "2026-07-16T15:00:00.000Z", status, notes: "Conferência fictícia." };
}

describe("regras monetárias", () => {
  it("calcula 2% sobre o valor originalmente aportado", () => expect(calculateCapitalRemuneration("10000000", 200)).toBe("200000"));
  it("não usa float em valores monetários", () => { expect(calculateCapitalRemuneration("999", 333)).toBe("33"); expect(cents("90071992547409931234567890") + 1n).toBe(90071992547409931234567891n); });
  it("rateia com soma exata e arredondamento determinístico", () => { const parts = proportionalSplit("100", ["1", "1", "1"]); expect(parts).toEqual(["34", "33", "33"]); expect(sumCents(parts)).toBe("100"); });
});

describe("migração do armazenamento demonstrativo", () => {
  it("migra a versão 2 separando contratos e entradas", () => {
    const legacy = { version: 2, investors: [], contributions: [], capitalRemunerationEvents: [], fundingSources: cloneDemoState().fundingSources, fundingLedgerEntries: cloneDemoState().fundingLedgerEntries, saleOperations: [{ id: "sale-old", contractCode: "CTR-OLD", maskedClientName: "Cliente O***", operationDate: "2026-01-01", releaseDate: "2026-01-02", principalAmount: "100000", financedAmount: "100000", releasedAmount: "100000", installmentAmount: "10000", termMonths: 12, interestRateBps: 200, status: "VALIDATED", bankValidationStatus: "VALIDATED", fundingValidationStatus: "VALID", responsibleUser: "Teste", notes: "", createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-02T00:00:00Z" }], saleFundingAllocations: [{ id: "alloc-old", saleOperationId: "sale-old", fundingSourceType: "REMO_OWN_CAPITAL", fundingSourceId: "src-remo", amount: "100000", allocationDate: "2026-01-01", historicalAvailableBalance: "25000000", validationStatus: "VALID", notes: "" }], fundingDivergences: [], operationalReceipts: [{ id: "receipt-old", contractCode: "CTR-OLD", installmentNumber: 1, receiptDate: "2026-02-01", totalPaid: "10000", principalAmount: "7000", interestAmount: "3000", iofAmount: "0", penaltyAmount: "0", discountAmount: "0", lossAmount: "0", status: "RECEIVED" }], allocationReceiptShares: [], treasuryEntries: [{ id: "mov-old", operationalReceiptId: "receipt-old", saleOperationId: "sale-old", type: "PMT_RECEIVED", direction: "ENTRADA", amount: "10000", date: "2026-02-01", competence: "2026-02", cashAccount: "Conta Demo", status: "CONFIRMADO", owner: "Teste", reference: "BANK-OLD", notes: "", createdAt: "2026-02-01T00:00:00Z" }], auditEvents: [], reconciliations: [] };
    const migrated = migrateFundingState(legacy);
    expect(migrated.version).toBe(4); expect(migrated.fundingContracts[0]).toMatchObject({ id: "sale-old", contractCode: "CTR-OLD" }); expect(migrated.treasuryIncomingReceipts[0]).toMatchObject({ id: "receipt-old", status: "VALIDATED" }); expect(migrated.treasuryEntries.find((item) => item.id === "mov-old")).toMatchObject({ fundingContractId: "sale-old", incomingReceiptId: "receipt-old", direction: "ENTRADA" });
  });
  it("carrega a chave v2 e persiste a versão v4", () => { const storage = new MemoryStorage(); storage.setItem(LEGACY_V2_STORAGE_KEY, JSON.stringify({ version: 2, saleOperations: [], saleFundingAllocations: [], fundingDivergences: [], operationalReceipts: [], allocationReceiptShares: [], treasuryEntries: [] })); const repo = repository(storage); expect(repo.getSnapshot().version).toBe(4); expect(JSON.parse(storage.getItem(FUNDING_STORAGE_KEY)!).version).toBe(4); });
  it("migra v3 sem duplicar recebimentos e remove a atribuição automática de IOF", () => {
    const storage = new MemoryStorage(); const current = cloneDemoState();
    const legacy = { ...current, version: 3, revenueDivergences: undefined, revenueColumnPreferences: undefined, allocationReceiptShares: current.allocationReceiptShares.map((share) => ({ ...share, iofShare: "500" })) };
    storage.setItem(LEGACY_V3_STORAGE_KEY, JSON.stringify(legacy)); const migrated = repository(storage).getSnapshot();
    expect(migrated.version).toBe(4); expect(migrated.treasuryIncomingReceipts).toHaveLength(current.treasuryIncomingReceipts.length); expect(migrated.allocationReceiptShares.every((item) => item.iofShare === "0" && item.iofDestinationStatus === "RULE_TO_CONFIRM")).toBe(true);
  });
  it("corrige uma liberação legada para saída durante a migração", () => {
    const migrated = migrateFundingState({
      version: 2,
      saleOperations: [], saleFundingAllocations: [], fundingDivergences: [], operationalReceipts: [], allocationReceiptShares: [],
      treasuryEntries: [{ id: "release-old", type: "LOAN_RELEASE", direction: "ENTRADA", amount: "100000", date: "2026-01-02", competence: "2026-01", cashAccount: "Conta Demo", status: "CONFIRMADO", owner: "Teste", reference: "REL-OLD", notes: "legado", createdAt: "2026-01-02T00:00:00Z" }],
    });
    expect(migrated.treasuryEntries[0]).toMatchObject({ id: "release-old", type: "LOAN_RELEASE", direction: "SAIDA" });
  });
  it("continua ignorando Prospects e migrando remuneração legada", () => { const base = cloneDemoState(); const legacy = { version: 1, prospects: [{ id: "pro-old" }], investors: base.investors.slice(0, 1), contributions: [{ ...base.contributions[0], monthlyRate: "2.00" }], dividendEvents: [{ id: "div-old", contributionId: "apt-demo-001", competence: "2026-08", dueDate: "2026-08-10", pjrAmount: "10000", status: "PREVISTO", notes: "legado" }] }; const migrated = migrateFundingState(legacy); expect("prospects" in migrated).toBe(false); expect(migrated.capitalRemunerationEvents[0]).toMatchObject({ id: "rem-old", grossAmount: "200000", netAmount: "190000" }); });
  it("mantém compatibilidade com a chave v1", () => { const storage = new MemoryStorage(); storage.setItem(LEGACY_FUNDING_STORAGE_KEY, JSON.stringify({ version: 1, prospects: [], investors: [], contributions: [], dividendEvents: [] })); expect(repository(storage).getSnapshot().version).toBe(4); });
});

describe("contratos e funding", () => {
  it("liberação de empréstimo cria saída, nunca entrada", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-OUT"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const entry = repo.confirmContractRelease(contract.id, { date: "2026-07-02", cashAccount: "Conta Demo", owner: "Teste", transactionReference: "REL-1", notes: "Liberação" }); expect(entry).toMatchObject({ type: "LOAN_RELEASE", direction: "SAIDA" }); expect(repo.getSnapshot().treasuryEntries.some((item) => item.fundingContractId === contract.id && item.direction === "ENTRADA")).toBe(false); });
  it("salva contrato com funding insuficiente e divergência", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-DIV"), [allocation("src-remo", "REMO_OWN_CAPITAL", "700000")]); expect(contract.status).toBe("FUNDING_DIVERGENT"); expect(repo.getSnapshot().fundingDivergences).toContainEqual(expect.objectContaining({ fundingContractId: contract.id, type: "FUNDING_TOTAL_MISMATCH", differenceAmount: "300000" })); });
  it("calcula saldo histórico por data", () => { const state = cloneDemoState(); state.fundingLedgerEntries.push({ id: "ret", fundingSourceId: "src-other", type: "RETURN", amount: "100000", date: "2026-05-01", reference: "ret" }, { id: "rein", fundingSourceId: "src-other", type: "REINTEGRATION", amount: "50000", date: "2026-06-01", reference: "rein" }); expect(calculateHistoricalAvailableBalance(state, "src-other", "2026-04-01")).toBe("7000000"); expect(calculateHistoricalAvailableBalance(state, "src-other", "2026-06-30")).toBe("6950000"); });
  it("permite múltiplos aportes por investidor", () => { const repo = repository(); const before = repo.getSnapshot().contributions.length; repo.createContribution(contributionInput("inv-demo-001", "100000")); repo.createContribution(contributionInput("inv-demo-001", "200000")); expect(repo.getSnapshot().contributions).toHaveLength(before + 2); });
});

describe("entradas, banco e conciliação N:N", () => {
  it("baixa operacional cria entrada pendente sem caixa", () => { const repo = repository(); const before = repo.getSnapshot().treasuryEntries.length; const contract = repo.createContract(contractInput("CTR-IN-1"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); expect(receipt.status).toBe("WAITING_BANK_VALIDATION"); expect(repo.getSnapshot().treasuryEntries).toHaveLength(before + 1); expect(repo.getSnapshot().treasuryEntries.some((item) => item.incomingReceiptId === receipt.id && item.direction === "ENTRADA")).toBe(false); });
  it("validação bancária correta confirma uma única entrada", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-IN-2"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); repo.reconcileBankMovement(movement("100000", "BANK-OK"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "ok" }]); const state = repo.getSnapshot(); expect(state.treasuryIncomingReceipts.find((item) => item.id === receipt.id)?.status).toBe("VALIDATED"); expect(state.treasuryEntries.filter((item) => item.incomingReceiptId === receipt.id && item.type === "PMT_RECEIVED")).toHaveLength(1); });
  it("diferença bancária cria divergência e pagamento parcial", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-IN-3"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); repo.reconcileBankMovement(movement("60000", "BANK-PART"), [{ incomingReceiptId: receipt.id, amount: "60000", notes: "parcial" }]); const state = repo.getSnapshot(); expect(state.treasuryIncomingReceipts.find((item) => item.id === receipt.id)?.status).toBe("PARTIALLY_VALIDATED"); expect(state.treasuryDivergences).toContainEqual(expect.objectContaining({ incomingReceiptId: receipt.id, type: "BANK_AMOUNT_MISMATCH", differenceAmount: "40000" })); });
  it("movimento não encontrado abre divergência", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-IN-4"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); repo.reconcileBankMovement(movement("0", "", "NOT_FOUND"), [{ incomingReceiptId: receipt.id, amount: "0", notes: "não localizado" }]); expect(repo.getSnapshot().treasuryIncomingReceipts.find((item) => item.id === receipt.id)?.status).toBe("BANK_MOVEMENT_NOT_FOUND"); expect(repo.getSnapshot().treasuryDivergences).toContainEqual(expect.objectContaining({ type: "BANK_MOVEMENT_NOT_FOUND" })); });
  it("concilia uma entrada com dois movimentos e soma exatamente", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-IN-5"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); repo.reconcileBankMovement(movement("60000", "BANK-1"), [{ incomingReceiptId: receipt.id, amount: "60000", notes: "parte 1" }]); repo.reconcileBankMovement(movement("40000", "BANK-2"), [{ incomingReceiptId: receipt.id, amount: "40000", notes: "parte 2" }]); const state = repo.getSnapshot(); const links = state.receiptBankReconciliations.filter((item) => item.incomingReceiptId === receipt.id && item.status === "ACTIVE"); expect(links).toHaveLength(2); expect(sumCents(links.map((item) => item.amount))).toBe("100000"); expect(state.treasuryIncomingReceipts.find((item) => item.id === receipt.id)?.status).toBe("VALIDATED"); });
  it("permite um movimento associado explicitamente a duas entradas", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-IN-6"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const first = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode, "60000")); const second = repo.createIncomingReceipt({ ...incomingInput(contract.id, contract.contractCode, "40000"), installmentNumber: 2 }); repo.reconcileBankMovement(movement("100000", "BANK-NN"), [{ incomingReceiptId: first.id, amount: "60000", notes: "primeira" }, { incomingReceiptId: second.id, amount: "40000", notes: "segunda" }]); const state = repo.getSnapshot(); expect(state.receiptBankReconciliations.filter((item) => item.bankMovementId === state.bankMovements.at(-1)?.id)).toHaveLength(2); expect(state.treasuryEntries.filter((item) => item.bankMovementId === state.bankMovements.at(-1)?.id && item.type === "PMT_RECEIVED")).toHaveLength(1); });
});

describe("Receita como projeção do mesmo recebimento", () => {
  it("Receita e Tesouraria referenciam o mesmo identificador central", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-REV-ID"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode));
    const revenue = repo.getRevenueRecords().find((item) => item.id === receipt.id);
    expect(revenue).toMatchObject({ id: receipt.id, operationalReceiptId: receipt.id, treasuryIncomingReceiptId: receipt.id });
    expect(repo.getSnapshot().treasuryIncomingReceipts.filter((item) => item.id === receipt.id)).toHaveLength(1);
  });
  it("calcula o total apurado e a diferença somente com bigint", () => {
    const receipt = { ...cloneDemoState().treasuryIncomingReceipts[0], paidAmountFromOperationalSource: "100000", principalAmount: "70000", interestAmount: "30000", iofAmount: "5000", penaltyAmount: "2000", discountAmount: "4000", lossAmount: "3000" };
    expect(calculateApuratedAmount(receipt)).toBe("100000"); expect(calculateComponentDifference(receipt)).toBe("0");
    expect(calculateApuratedAmount({ ...receipt, paidAmountFromOperationalSource: "100001" })).toBe("100000"); expect(calculateComponentDifference({ ...receipt, paidAmountFromOperationalSource: "100001" })).toBe("-1");
  });
  it("mantém valores divergentes e cria RECEIPT_COMPONENT_MISMATCH", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-COMP"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]);
    const receipt = repo.createIncomingReceipt({ ...incomingInput(contract.id, contract.contractCode), principalAmount: "60000", interestAmount: "30000" });
    expect(repo.getRevenueRecords().find((item) => item.id === receipt.id)).toMatchObject({ apuratedAmount: "90000", componentDifference: "-10000", revenueStatus: "COMPONENT_DIVERGENCE" });
    expect(repo.getSnapshot().revenueDivergences).toContainEqual(expect.objectContaining({ incomingReceiptId: receipt.id, type: "RECEIPT_COMPONENT_MISMATCH", differenceAmount: "10000" }));
  });
  it("uma validação bancária atualiza imediatamente Receita e Tesouraria", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-SHARED"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode));
    expect(repo.getRevenueRecords().find((item) => item.id === receipt.id)?.bankValidationStatus).toBe("PENDING");
    repo.reconcileBankMovement(movement("100000", "BANK-SHARED"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "mesmo vínculo" }]);
    expect(repo.getRevenueRecords().find((item) => item.id === receipt.id)).toMatchObject({ bankValidationStatus: "VALIDATED", reconciliationStatus: "RECONCILED" });
    expect(repo.getSnapshot().treasuryIncomingReceipts.find((item) => item.id === receipt.id)?.bankValidationStatus).toBe("VALIDATED");
  });
  it("bloqueia movimento bancário duplicado e não duplica caixa", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-NODUP"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); const input = movement("100000", "BANK-UNIQUE");
    repo.reconcileBankMovement(input, [{ incomingReceiptId: receipt.id, amount: "100000", notes: "primeiro" }]); const before = repo.getSnapshot().treasuryEntries.filter((item) => item.type === "PMT_RECEIVED" && item.status === "CONFIRMADO").length;
    expect(() => repo.reconcileBankMovement(input, [{ incomingReceiptId: receipt.id, amount: "100000", notes: "duplicado" }])).toThrow("já foi registrado");
    expect(repo.getSnapshot().treasuryEntries.filter((item) => item.type === "PMT_RECEIVED" && item.status === "CONFIRMADO")).toHaveLength(before);
  });
  it("consolida uma tentativa de baixa duplicada no registro central existente", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-RECEIPT-DUP"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const input = incomingInput(contract.id, contract.contractCode); const first = repo.createIncomingReceipt(input); const before = repo.getSnapshot().treasuryIncomingReceipts.length; const second = repo.createIncomingReceipt(input);
    expect(second.id).toBe(first.id); expect(repo.getSnapshot().treasuryIncomingReceipts).toHaveLength(before); expect(repo.getSnapshot().revenueDivergences).toContainEqual(expect.objectContaining({ incomingReceiptId: first.id, type: "DUPLICATED_RECEIPT" }));
  });
  it("filtra competência mensal pela referência explícita", () => {
    const state = cloneDemoState(); const august = buildRevenueRecords(state).filter((item) => item.paymentReference.competence === "2026-08");
    expect(august.length).toBeGreaterThan(0); expect(august.every((item) => item.paymentReference.competence === "2026-08")).toBe(true);
  });
});

describe("rateio histórico e auditoria", () => {
  it("rateia principal e juros incluindo capital próprio REMO", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-SHARE"), [allocation("src-other", "OTHER_SOURCE", "600000"), allocation("src-remo", "REMO_OWN_CAPITAL", "400000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); repo.reconcileBankMovement(movement("100000", "BANK-SHARE"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "total" }]); const shares = repo.getSnapshot().allocationReceiptShares.filter((item) => item.incomingReceiptId === receipt.id); expect(sumCents(shares.map((item) => item.principalShare))).toBe("70000"); expect(sumCents(shares.map((item) => item.interestShare))).toBe("30000"); expect(shares).toContainEqual(expect.objectContaining({ fundingSourceType: "REMO_OWN_CAPITAL", principalShare: "28000", interestShare: "12000" })); });
  it("rateia desconto e prejuízo entre múltiplos investidores com soma exata e deixa IOF sem atribuição", () => {
    const repo = repository(); const contract = repo.createContract(contractInput("CTR-MULTI"), [
      { ...allocation("src-apt-001", "INVESTOR_CONTRIBUTION", "500000"), investorId: "inv-demo-001", contributionId: "apt-demo-001" },
      { ...allocation("src-apt-003", "INVESTOR_CONTRIBUTION", "300000"), investorId: "inv-demo-002", contributionId: "apt-demo-003" },
      allocation("src-remo", "REMO_OWN_CAPITAL", "200000"),
    ]);
    const receipt = repo.createIncomingReceipt({ ...incomingInput(contract.id, contract.contractCode), principalAmount: "70000", interestAmount: "30000", iofAmount: "5000", penaltyAmount: "2000", discountAmount: "4000", lossAmount: "3000" });
    repo.reconcileBankMovement(movement("100000", "BANK-MULTI"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "total" }]);
    const shares = repo.getSnapshot().allocationReceiptShares.filter((item) => item.incomingReceiptId === receipt.id && item.status !== "REVERSED");
    expect(new Set(shares.flatMap((item) => item.investorId ? [item.investorId] : [])).size).toBe(2); expect(shares).toContainEqual(expect.objectContaining({ fundingSourceType: "REMO_OWN_CAPITAL" }));
    expect(sumCents(shares.map((item) => item.principalShare))).toBe("70000"); expect(sumCents(shares.map((item) => item.interestShare))).toBe("30000"); expect(sumCents(shares.map((item) => item.discountShare))).toBe("4000"); expect(sumCents(shares.map((item) => item.lossShare))).toBe("3000");
    expect(shares.every((item) => item.iofShare === "0" && item.iofDestinationStatus === "RULE_TO_CONFIRM")).toBe(true);
  });
  it("usa a composição válida na baixa, não a composição corrigida depois", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-HISTORY"), [allocation("src-other", "OTHER_SOURCE", "600000"), allocation("src-remo", "REMO_OWN_CAPITAL", "400000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode, "100000", "2026-07-15")); repo.reviseContractFunding(contract.id, [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000", "2026-07-01")], "Teste"); repo.reconcileBankMovement(movement("100000", "BANK-HISTORY"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "total" }]); const shares = repo.getSnapshot().allocationReceiptShares.filter((item) => item.incomingReceiptId === receipt.id); expect(shares).toHaveLength(2); expect(shares.some((item) => item.fundingSourceType === "OTHER_SOURCE")).toBe(true); });
  it("estorno preserva movimento, associações e auditoria", () => { const repo = repository(); const contract = repo.createContract(contractInput("CTR-REV"), [allocation("src-remo", "REMO_OWN_CAPITAL", "1000000")]); const receipt = repo.createIncomingReceipt(incomingInput(contract.id, contract.contractCode)); const bank = repo.reconcileBankMovement(movement("100000", "BANK-REV"), [{ incomingReceiptId: receipt.id, amount: "100000", notes: "total" }]); repo.reverseBankMovement(bank.id, { date: "2026-07-20", owner: "Teste", notes: "estorno" }); const state = repo.getSnapshot(); expect(state.bankMovements.find((item) => item.id === bank.id)?.status).toBe("REVERSED"); expect(state.receiptBankReconciliations.find((item) => item.bankMovementId === bank.id)?.status).toBe("REVERSED"); expect(state.auditEvents).toContainEqual(expect.objectContaining({ entityId: bank.id, action: "ESTORNO" })); });
  it("pagamento de remuneração continua criando saída", () => { const repo = repository(); repo.payCapitalRemuneration("rem-demo-003", { date: "2026-07-31", cashAccount: "Conta Demo", owner: "Teste", notes: "pago" }); expect(repo.getSnapshot().treasuryEntries).toContainEqual(expect.objectContaining({ capitalRemunerationEventId: "rem-demo-003", type: "CAPITAL_REMUNERATION_PAID", direction: "SAIDA" })); });
  it("persiste e restaura o localStorage demonstrativo", () => { const storage = new MemoryStorage(); const first = repository(storage); first.createContribution(contributionInput("inv-demo-001", "123456")); const second = repository(storage); expect(second.getSnapshot().contributions.some((item) => item.originalAmount === "123456")).toBe(true); second.restoreDemoData(); expect(second.getSnapshot().contributions).toHaveLength(cloneDemoState().contributions.length); });
});
