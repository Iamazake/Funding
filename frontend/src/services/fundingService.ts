import { MockFundingDataProvider } from "@/providers/mockFundingProvider";
import type {
  AllocationsDataProvider, ContributionsDataProvider, FundingDashboardDataProvider,
  InvestorsDataProvider, OperationalContractsDataProvider, TreasuryDataProvider,
} from "@/types/funding";

export interface FundingDataServices {
  dashboard: FundingDashboardDataProvider;
  investors: InvestorsDataProvider;
  contributions: ContributionsDataProvider;
  allocations: AllocationsDataProvider;
  treasury: TreasuryDataProvider;
  contracts: OperationalContractsDataProvider;
}

const mockProvider = new MockFundingDataProvider();

export const fundingService: FundingDataServices = {
  dashboard: mockProvider,
  investors: mockProvider,
  contributions: mockProvider,
  allocations: mockProvider,
  treasury: mockProvider,
  contracts: mockProvider,
};
