import {
  mockAllocations,
  mockContributions,
  mockContracts,
  mockDashboard,
  mockInvestors,
  mockRemunerations,
  mockReports,
  mockTreasury,
  mockTreasuryMovements,
} from "@/data/mockFundingData";
import { centsToMoney, parseMoneyToCents } from "@/lib/formatters";
import type {
  Allocation,
  AllocationSimulation,
  AllocationSimulationResult,
  AllocationsDataProvider,
  Contribution,
  ContributionsDataProvider,
  FundingDashboardData,
  FundingDashboardDataProvider,
  Investor,
  InvestorDetail,
  InvestorsDataProvider,
  OperationalContract,
  OperationalContractsDataProvider,
  ReportSnapshot,
  TreasuryDataProvider,
  TreasurySummary,
} from "@/types/funding";

const wait = (milliseconds = 160) => new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

export class MockFundingDataProvider
  implements FundingDashboardDataProvider, InvestorsDataProvider, ContributionsDataProvider,
    AllocationsDataProvider, TreasuryDataProvider, OperationalContractsDataProvider {
  private contributions = structuredClone(mockContributions);
  private contracts = structuredClone(mockContracts);
  private allocations = structuredClone(mockAllocations);

  async getDashboard(): Promise<FundingDashboardData> { await wait(); return structuredClone(mockDashboard); }
  async listInvestors(): Promise<Investor[]> { await wait(); return structuredClone(mockInvestors); }
  async listContributions(): Promise<Contribution[]> { await wait(); return structuredClone(this.contributions); }
  async listAllocations(): Promise<Allocation[]> { await wait(); return structuredClone(this.allocations); }
  async listContracts(): Promise<OperationalContract[]> { await wait(); return structuredClone(this.contracts); }
  async getTreasury(): Promise<TreasurySummary> { await wait(); return structuredClone(mockTreasury); }
  async getReports(): Promise<ReportSnapshot> { await wait(); return structuredClone(mockReports); }

  async getContribution(id: string): Promise<Contribution | null> {
    await wait();
    return structuredClone(this.contributions.find((item) => item.id === id) ?? null);
  }

  async getContract(id: string): Promise<OperationalContract | null> {
    await wait();
    return structuredClone(this.contracts.find((item) => item.id === id) ?? null);
  }

  async getInvestor(id: string): Promise<InvestorDetail | null> {
    await wait();
    const investor = mockInvestors.find((item) => item.id === id);
    if (!investor) return null;
    return structuredClone({
      ...investor,
      contributions: this.contributions.filter((item) => item.investorId === id),
      allocations: this.allocations.filter((item) => item.investorId === id),
      remunerations: mockRemunerations.filter((item) => item.investorId === id),
      movements: mockTreasuryMovements.filter((item) => item.investorId === id),
      evolution: [
        { label: "Fev", value: 100 }, { label: "Mar", value: 102 }, { label: "Abr", value: 104 },
        { label: "Mai", value: 107 }, { label: "Jun", value: 110 }, { label: "Jul", value: 114 },
      ],
    });
  }

  async simulateAllocation(input: AllocationSimulation): Promise<AllocationSimulationResult> {
    await wait(260);
    const contract = this.contracts.find((item) => item.id === input.contractId);
    if (!contract) return { success: false, message: "Contrato demonstrativo não encontrado.", allocatedAmount: "0.00", remainingAmount: "0.00" };

    const required = parseMoneyToCents(contract.requiredFunding);
    const alreadyAllocated = parseMoneyToCents(contract.allocatedFunding);
    const remainingBefore = required - alreadyAllocated;
    let requested = 0n;

    for (const item of input.items) {
      const contribution = this.contributions.find((candidate) => candidate.id === item.contributionId);
      if (!contribution) return { success: false, message: "Aporte demonstrativo não encontrado.", allocatedAmount: "0.00", remainingAmount: centsToMoney(remainingBefore) };
      const amount = parseMoneyToCents(item.amount);
      if (amount < 0n || amount > parseMoneyToCents(contribution.availableAmount)) {
        return { success: false, message: `O valor excede o saldo livre de ${contribution.code}.`, allocatedAmount: "0.00", remainingAmount: centsToMoney(remainingBefore) };
      }
      requested += amount;
    }

    if (requested === 0n) return { success: false, message: "Informe ao menos uma alocação.", allocatedAmount: "0.00", remainingAmount: centsToMoney(remainingBefore) };
    if (requested > remainingBefore) return { success: false, message: "O total excede o funding ainda necessário.", allocatedAmount: "0.00", remainingAmount: centsToMoney(remainingBefore) };

    input.items.forEach((item, index) => {
      const contribution = this.contributions.find((candidate) => candidate.id === item.contributionId);
      if (!contribution) return;
      const amount = parseMoneyToCents(item.amount);
      if (amount === 0n) return;
      const newAvailable = parseMoneyToCents(contribution.availableAmount) - amount;
      contribution.availableAmount = centsToMoney(newAvailable);
      contribution.allocatedAmount = centsToMoney(parseMoneyToCents(contribution.allocatedAmount) + amount);
      contribution.status = newAvailable === 0n ? "allocated" : "partially_allocated";
      this.allocations.push({
        id: `rat-session-${Date.now()}-${index}`, investorId: contribution.investorId,
        investorName: contribution.investorName, contributionId: contribution.id,
        contractId: contract.id, contractCode: contract.code, amount: item.amount,
        allocatedAt: "2026-07-31", status: "active",
      });
    });

    const newAllocated = alreadyAllocated + requested;
    const remaining = required - newAllocated;
    contract.allocatedFunding = centsToMoney(newAllocated);
    contract.fundedPercent = `${newAllocated * 10000n / required / 100n}.${(newAllocated * 10000n / required % 100n).toString().padStart(2, "0")}`;
    contract.status = remaining === 0n ? "funded" : "partial";
    return { success: true, message: "Rateio aplicado somente ao estado mockado desta sessão.", allocatedAmount: centsToMoney(requested), remainingAmount: centsToMoney(remaining) };
  }
}
