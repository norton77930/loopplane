import {
  WEB_CONTRACT_VERSION,
  generatedAgentControlFixtures,
  generatedApiResponseFixtures,
  generatedCapabilityFixtures,
  generatedSessionEventFixtures,
} from "../api/generated";
import type {
  AgentControlProjection,
  BulkDeleteResult,
  CapabilityOperationResult,
  CapabilitySettingsStatus,
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

    expect(WEB_CONTRACT_VERSION).toBe("077-web-agent-controls");
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
    const settings: CapabilitySettingsStatus =
      generatedCapabilityFixtures.settings;

    expect(memory.kind).toBe("user");
    expect(memory.scope).toBe("owned");
    expect(memory.actions).toContain("update");
    expect(skill.source).toBe("managed");
    expect(skill.problem).toBeNull();
    expect(mcp.status).toBe("disconnected");
    expect(mcp.actions).toContain("reconnect");
    expect(context.workspace_label).toBe("docs-repo");
    expect(context.scope).toBe("owned");
    expect(schedule.enabled).toBe(true);
    expect(schedule.instruction).toBe("refresh documentation notes");
    expect(modelDefault.model_id).toBe("model-a");
    expect(modelDefault.updated_at).toBeNull();
    expect(result.ok).toBe(true);
    expect(settings.storage_available).toBe(true);
    expect(settings.mutations_enabled).toBe(true);
    expect(settings.runtime_activation_enabled).toBe(true);
    expect(settings.mcp_endpoint_policy_available).toBe(true);
    expect(settings.schedule_runner_available).toBe(true);
  });
  it("wraps backend-owned agent-control fixtures without enum drift", () => {
    const projection: AgentControlProjection =
      generatedAgentControlFixtures.projection;

    expect(projection.permission.selectable_modes[0].kind).toBe("plan");
    expect(projection.permission.rule_default).toBeNull();
    expect(projection.budget.pricing).toBe("unknown");
    expect(generatedAgentControlFixtures.run_request.uploads).toEqual([
      { reference: "upload://opaque" },
    ]);
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
