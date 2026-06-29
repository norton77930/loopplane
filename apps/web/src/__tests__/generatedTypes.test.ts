import {
  WEB_CONTRACT_VERSION,
  generatedApiResponseFixtures,
  generatedCapabilityFixtures,
  generatedSessionEventFixtures,
} from "../api/generated";
import type {
  BulkDeleteResult,
  CapabilityOperationResult,
  ForkSessionRequest,
  ManagedSchedule,
  ManagedSkill,
  McpConfiguration,
  MemoryCapability,
  ModelDefault,
  RawEvent,
  WorkspaceContext,
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

    expect(WEB_CONTRACT_VERSION).toBe("075-web-capability-management");
    expect(summary.session_id).toBe("session-1");
    expect(summary.starred).toBe(true);
    expect(bulkDelete.deleted).toEqual(["session-1"]);
    expect(forkRequest.sequence).toBe(1);
  });

  it("wraps backend-owned capability fixtures through public API types", () => {
    const memory: MemoryCapability = generatedCapabilityFixtures.memory;
    const skill: ManagedSkill = generatedCapabilityFixtures.skill;
    const mcp: McpConfiguration = generatedCapabilityFixtures.mcp;
    const context: WorkspaceContext = generatedCapabilityFixtures.context;
    const schedule: ManagedSchedule = generatedCapabilityFixtures.schedule;
    const modelDefault: ModelDefault = generatedCapabilityFixtures.model_default;
    const result: CapabilityOperationResult = generatedCapabilityFixtures.result;

    expect(memory.kind).toBe("user");
    expect(skill.source).toBe("managed");
    expect(mcp.status).toBe("disconnected");
    expect(context.workspace_label).toBe("docs-repo");
    expect(schedule.enabled).toBe(true);
    expect(modelDefault.model_id).toBe("model-a");
    expect(result.ok).toBe(true);
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
