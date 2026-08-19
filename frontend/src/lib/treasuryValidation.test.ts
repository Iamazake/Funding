import { describe, expect, it } from "vitest";

import { treasuryValidationPreview, treasuryValidationReady } from "@/lib/treasuryValidation";

describe("validação bancária manual", () => {
  it.each([
    ["300,00", 0n, "VALIDATED"],
    ["305,00", 500n, "DIVERGENT"],
    ["295,00", -500n, "DIVERGENT"],
  ] as const)("calcula diferença segura para %s", (observed, difference, status) => {
    const preview = treasuryValidationPreview("300.00", observed);
    expect(preview?.differenceCents).toBe(difference);
    expect(preview?.status).toBe(status);
  });

  it("exige justificativa apenas quando a prévia é divergente", () => {
    const valid = treasuryValidationPreview("300.00", "300,00");
    const divergent = treasuryValidationPreview("300.00", "295,00");
    expect(treasuryValidationReady(valid, "2026-08-18", "")).toBe(true);
    expect(treasuryValidationReady(divergent, "2026-08-18", "")).toBe(false);
    expect(treasuryValidationReady(divergent, "2026-08-18", "Tarifa bancária")).toBe(true);
  });
});
