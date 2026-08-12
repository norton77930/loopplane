import { describe, expect, it, vi } from "vitest";

import { DesktopPresentationHost } from "../presentation-host";

const api = {
  inspection: {
    get: vi.fn().mockResolvedValue({
      session_id: "session-1",
      skills: [{ name: "writer", available: true }],
      tools: [],
      mcp: [],
      memory: [],
      unavailable: false,
    }),
  },
  agentControls: {
    get: vi.fn().mockResolvedValue({
      default_mode: null,
      selectable_modes: [],
      active_run: null,
      last_accepted_run: null,
      budget: { tracking: "unavailable", pricing: "unpriced" },
      actions: [],
      unavailable: false,
    }),
  },
  capabilities: {
    list: vi.fn().mockResolvedValue({
      capabilities: [{ id: "mcp", label: "MCP", available: false, actions: [], status: "unavailable" }],
    }),
    invokeAction: vi.fn(),
  },
} as const;

describe("DesktopPresentationHost inspection projection", () => {
  it("marks unsupported cost, context, uploads, and artifacts unavailable", async () => {
    const host = new DesktopPresentationHost(api as never);

    await expect(host.getInspection("session-1")).resolves.toMatchObject({
      cost: { status: "unavailable" },
      context: { status: "unavailable" },
      uploads: { status: "unavailable" },
      artifacts: { status: "unavailable" },
    });
    await expect(host.getCapabilities()).resolves.toEqual([
      { id: "mcp", label: "MCP", available: false, actions: [], status: "unavailable" },
    ]);
  });
});
