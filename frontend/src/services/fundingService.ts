import { useSyncExternalStore } from "react";

import { createBrowserFundingRepository } from "@/repositories/fundingRepository";
import { buildRevenueRecords } from "@/lib/revenue";
import type { FundingState, RevenueRecordView, TreasurySummary } from "@/types/funding";

export const fundingRepository = createBrowserFundingRepository();

let cachedSnapshot: FundingState = fundingRepository.getSnapshot();

fundingRepository.subscribe(() => {
  cachedSnapshot = fundingRepository.getSnapshot();
});

export function useFundingState(): FundingState {
  return useSyncExternalStore(
    (listener) => fundingRepository.subscribe(listener),
    () => cachedSnapshot,
    () => cachedSnapshot,
  );
}

export function getTreasurySummary(): TreasurySummary {
  return fundingRepository.getTreasurySummary();
}

export function useRevenueRecords(): RevenueRecordView[] {
  return buildRevenueRecords(useFundingState());
}
