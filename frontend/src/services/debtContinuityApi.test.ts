import { afterEach, describe, expect, it, vi } from "vitest";

import { debtContinuityApi } from "@/services/debtContinuityApi";

afterEach(() => vi.restoreAllMocks());

describe("cockpit de continuidade da dívida", () => {
  it("usa o endpoint REFIN existente com predecessor e sucessor canônicos", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      id: "continuity-1",
      continuity_type: "REFINANCING",
      status: "REFIN_CONFIRMED",
    }), { status: 201, headers: { "Content-Type": "application/json" } }));

    await debtContinuityApi.createRefinancing({
      predecessor_sale_identity_id: "00000000-0000-0000-0000-000000000001",
      successor_sale_identity_id: "00000000-0000-0000-0000-000000000002",
      effective_date: "2026-08-27",
      notes: "Confirmado no cockpit bancário.",
      principal_rolled: null,
    });

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toContain("/refinancings");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      predecessor_sale_identity_id: "00000000-0000-0000-0000-000000000001",
      successor_sale_identity_id: "00000000-0000-0000-0000-000000000002",
    });
  });

  it("registra e confirma RENEG sem enviar dinheiro novo", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "continuity-2",
        continuity_type: "RENEGOTIATION",
        status: "REVIEW_REQUIRED",
      }), { status: 201, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "continuity-2",
        continuity_type: "RENEGOTIATION",
        status: "RENEGOTIATION_CONFIRMED",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));

    const review = await debtContinuityApi.createRenegotiationReview({
      source_batch_id: 4,
      successor_sale_identity_id: "00000000-0000-0000-0000-000000000002",
      candidate_predecessor_sale_identity_ids: ["00000000-0000-0000-0000-000000000001"],
      continuity_type: "RENEGOTIATION",
      scope: "NEW_CONTRACT",
      effective_date: "2026-08-27",
      reason: "Saldo reprogramado pela REMO.",
      evidence: { cockpit: "TREASURY_BANK_VALIDATION" },
    });
    await debtContinuityApi.confirmRenegotiation(review.id, {
      predecessor_sale_identity_id: "00000000-0000-0000-0000-000000000001",
      original_principal: "300.00",
      principal_paid: "200.00",
      principal_rolled: "100.00",
      interest_paid: "0.00",
      has_new_disbursement: false,
      effective_date: "2026-08-27",
      evidence: { cockpit: "TREASURY_BANK_VALIDATION" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain("/reviews");
    expect(fetchMock.mock.calls[1][0]).toContain("/continuity-2/confirm");
    const confirmPayload = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    expect(confirmPayload.has_new_disbursement).toBe(false);
    expect(confirmPayload).not.toHaveProperty("released_amount");
    expect(confirmPayload).not.toHaveProperty("observed_amount");
  });
});
