/**
 * CoworkPresentationHost conformance (078 T057).
 */

import { describe, expect, it } from "vitest";

import {
  defaultCapabilityMap,
  isAllowlistedCapabilityAction,
  type CoworkPresentationHost,
} from "../host";
import type {
  PresentationAgentControls,
  PresentationCapability,
  PresentationInspection,
  PresentationSessionSummary,
} from "../models";

function createConformingHost(): CoworkPresentationHost & { calls: string[] } {
  const calls: string[] = [];
  const caps: PresentationCapability[] = [
    {
      id: "memory",
      label: "Memory",
      available: true,
      actions: ["refresh"],
      status: "available",
    },
    {
      id: "mcp",
      label: "MCP",
      available: false,
      actions: [],
      status: "unavailable",
    },
  ];
  return {
    calls,
    capabilities: () => defaultCapabilityMap(),
    async listSessions(): Promise<PresentationSessionSummary[]> {
      calls.push("listSessions");
      return [{ id: "s1", title: "Demo", starred: false, projectId: null }];
    },
    async getCapabilities() {
      calls.push("getCapabilities");
      return caps;
    },
    async invokeCapabilityAction(capabilityId, action) {
      calls.push(`invoke:${capabilityId}:${action}`);
      if (!isAllowlistedCapabilityAction(capabilityId, action, caps)) {
        throw new Error("unsupported_capability_action");
      }
      return caps;
    },
    async getInspection(sessionId): Promise<PresentationInspection> {
      calls.push(`inspection:${sessionId}`);
      return {
        sessionId,
        skills: [],
        tools: [{ name: "echo", available: true }],
        mcp: [],
        memory: [],
        unavailable: false,
      };
    },
    async getAgentControls(sessionId): Promise<PresentationAgentControls> {
      calls.push(`agentControls:${sessionId}`);
      return {
        sessionId,
        defaultMode: "acceptEdits",
        selectableModes: [
          { id: "acceptEdits", kind: "standard", summary: "permission.mode.accept_edits" },
        ],
        activeRun: null,
        lastAcceptedRun: null,
        budget: {
          tracking: "unavailable",
          pricing: "unpriced",
          sessionGuard: "unknown",
          monthlyGuard: "unknown",
        },
        actions: [],
        unavailable: false,
      };
    },
    subscribeProgress(sessionId, _onEvent) {
      calls.push(`subscribe:${sessionId}`);
      return () => calls.push(`unsubscribe:${sessionId}`);
    },
    async submit(sessionId, prompt) {
      calls.push(`submit:${sessionId}:${prompt}`);
    },
    async answerApproval(requestId, allow) {
      calls.push(`answerApproval:${requestId}:${allow}`);
    },
    async answerQuestion(requestId, answers) {
      calls.push(`answerQuestion:${requestId}:${answers.join(",")}`);
    },
    async cancel(sessionId) {
      calls.push(`cancel:${sessionId}`);
    },
  };
}

describe("CoworkPresentationHost conformance", () => {
  it("exposes capability map without claiming backup", () => {
    const host = createConformingHost();
    const map = host.capabilities();
    expect(map.sessions).toBe(true);
    expect(map.inspection).toBe(true);
    expect(map.agentControls).toBe(true);
    expect(map.backup).toBe(false);
  });

  it("lists sessions and capabilities with honest unavailable", async () => {
    const host = createConformingHost();
    const sessions = await host.listSessions();
    expect(sessions[0]?.id).toBe("s1");
    const caps = await host.getCapabilities();
    expect(caps.find((c) => c.id === "mcp")?.available).toBe(false);
    expect(caps.find((c) => c.id === "mcp")?.status).toBe("unavailable");
  });

  it("rejects unsupported capability actions", async () => {
    const host = createConformingHost();
    await expect(
      host.invokeCapabilityAction("mcp", "refresh"),
    ).rejects.toThrow(/unsupported/i);
    await expect(
      host.invokeCapabilityAction("memory", "delete_everything"),
    ).rejects.toThrow(/unsupported/i);
    await expect(host.invokeCapabilityAction("memory", "refresh")).resolves.toBeTruthy();
  });

  it("inspection and agent controls stay public-safe shaped", async () => {
    const host = createConformingHost();
    const insp = await host.getInspection("s1");
    expect(insp.unavailable).toBe(false);
    expect(JSON.stringify(insp)).not.toMatch(/password|secret|C:\\\\/i);
    const ac = await host.getAgentControls("s1");
    expect(ac.budget.pricing).toBe("unpriced");
    expect(ac.defaultMode).toBe("acceptEdits");
  });

  it("subscribe/unsubscribe is local and does not invent RPC ids", () => {
    const host = createConformingHost();
    const unsub = host.subscribeProgress("s1", () => undefined);
    unsub();
    expect(host.calls).toEqual(["subscribe:s1", "unsubscribe:s1"]);
    expect(host.calls.join(" ")).not.toContain("mutation");
  });
});
