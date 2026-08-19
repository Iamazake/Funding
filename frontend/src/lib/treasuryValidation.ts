import { brazilianMoneyToDecimal, decimalMoneyToCents } from "@/lib/fundingFormat";
import type { TreasuryValidationStatus } from "@/types/treasuryApi";

export interface TreasuryValidationPreview {
  observedAmount: string;
  differenceCents: bigint;
  status: Exclude<TreasuryValidationStatus, "PENDING">;
}

export function treasuryValidationPreview(
  systemAmount: string | null,
  observedInput: string,
): TreasuryValidationPreview | null {
  const observedAmount = brazilianMoneyToDecimal(observedInput);
  const systemCents = systemAmount ? decimalMoneyToCents(systemAmount) : null;
  const observedCents = observedAmount ? decimalMoneyToCents(observedAmount) : null;
  if (!observedAmount || systemCents === null || observedCents === null) return null;
  const differenceCents = observedCents - systemCents;
  return {
    observedAmount,
    differenceCents,
    status: differenceCents === 0n ? "VALIDATED" : "DIVERGENT",
  };
}

export function treasuryValidationReady(
  preview: TreasuryValidationPreview | null,
  observedDate: string,
  justification: string,
): boolean {
  return Boolean(
    preview
    && observedDate
    && (preview.status === "VALIDATED" || justification.trim()),
  );
}
