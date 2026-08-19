import { API_URL, notifyIfUnauthorized } from "@/lib/api";
import type {
  ContributionAnalysis,
  FundingContribution,
  FundingContributionInput,
  FundingInvestor,
  FundingInvestorInput,
  FundingSource,
  LedgerEntry,
  RevenueDistribution,
  SaleFundingComposition,
  SourceBalance,
} from "@/types/fundingApi";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/funding${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  notifyIfUnauthorized(response.status);
  if (!response.ok) {
    let message = "Não foi possível acessar a API de Funding.";
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg: string }> };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) message = payload.detail.map((item) => item.msg).join(" ");
    } catch {
      // Preserve the friendly connection/API error above.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const fundingApi = {
  listInvestors: () => request<FundingInvestor[]>("/investors"),
  getInvestor: (id: string) => request<FundingInvestor>(`/investors/${encodeURIComponent(id)}`),
  createInvestor: (input: FundingInvestorInput) => request<FundingInvestor>("/investors", { method: "POST", body: JSON.stringify(input) }),
  updateInvestor: (id: string, input: Partial<FundingInvestorInput>) => request<FundingInvestor>(`/investors/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(input) }),
  listContributions: (investorId?: string) => request<FundingContribution[]>(investorId ? `/investors/${encodeURIComponent(investorId)}/contributions` : "/contributions"),
  getContribution: (id: string) => request<FundingContribution>(`/contributions/${encodeURIComponent(id)}`),
  getContributionAnalysis: (id: string) => request<ContributionAnalysis>(`/contributions/${encodeURIComponent(id)}/analysis`),
  createContribution: (input: FundingContributionInput) => request<FundingContribution>("/contributions", { method: "POST", body: JSON.stringify(input) }),
  updateContribution: (id: string, input: Partial<FundingContributionInput>) => request<FundingContribution>(`/contributions/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(input) }),
  listSources: () => request<FundingSource[]>("/sources"),
  getSourceBalance: (id: string, asOf?: string) => request<SourceBalance>(`/sources/${encodeURIComponent(id)}/balance${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`),
  getSourceLedger: (id: string) => request<LedgerEntry[]>(`/sources/${encodeURIComponent(id)}/ledger`),
  getSaleComposition: (saleId: string) => request<SaleFundingComposition>(`/sales/${encodeURIComponent(saleId)}/composition`),
  createAllocation: (saleId: string, input: { source_id: string; amount: string; notes: string | null }) => request<SaleFundingComposition>(`/sales/${encodeURIComponent(saleId)}/allocations`, { method: "POST", body: JSON.stringify(input) }),
  reverseAllocation: (allocationId: string, input: { reason: string }) => request<SaleFundingComposition>(`/allocations/${encodeURIComponent(allocationId)}/reversal`, { method: "POST", body: JSON.stringify(input) }),
  registerRemoCapital: (input: { amount: string; effective_date: string; direction: "CREDIT" | "DEBIT"; notes: string }) => request<LedgerEntry>("/sources/remo-capital/entries", { method: "POST", body: JSON.stringify(input) }),
  getRevenueDistribution: (revenueId: string | number) => request<RevenueDistribution>(`/revenue/${encodeURIComponent(String(revenueId))}/distribution`),
  distributeRevenue: (revenueId: string | number, input: { notes: string | null }) => request<RevenueDistribution>(`/revenue/${encodeURIComponent(String(revenueId))}/distribute`, { method: "POST", body: JSON.stringify(input) }),
  reverseRevenueDistribution: (distributionId: string, input: { reason: string }) => request<RevenueDistribution>(`/revenue/distributions/${encodeURIComponent(distributionId)}/reversal`, { method: "POST", body: JSON.stringify(input) }),
};
