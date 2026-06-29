import {
  WEB_CONTRACT_VERSION,
  generatedApiResponseFixtures,
  generatedSessionEventFixtures,
} from "../api/generated";
import type {
  BulkDeleteResult,
  ForkSessionRequest,
  RawEvent,
  SessionSummary,
} from "../api/types";

describe("generated web contract types", () => {
  it("wraps backend-owned response fixtures through the public API types", () => {
    const summary: SessionSummary = generatedApiResponseFixtures.session_summary;
    const bulkDelete: BulkDeleteResult =
      generatedApiResponseFixtures.bulk_delete_result;
    const forkRequest: ForkSessionRequest = {
      sequence: 1,
      title: null,
      model: "model-a",
    };

    expect(WEB_CONTRACT_VERSION).toBe("074-web-parity-foundation");
    expect(summary.session_id).toBe("session-1");
    expect(summary.starred).toBe(true);
    expect(bulkDelete.deleted).toEqual(["session-1"]);
    expect(forkRequest.sequence).toBe(1);
  });

  it("wraps backend-owned event fixtures through the shared event type", () => {
    const event: RawEvent = generatedSessionEventFixtures.run_terminated;

    expect(event.type).toBe("run-terminated");
    expect(event.payload).toEqual({
      reason: "natural-completion",
      turns_taken: 1,
    });
  });
});
