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

describe("DesktopPresentationHost progress isolation", () => {
  it("subscribes to the active interaction id and routes progress only to its session", async () => {
    const subscribedIds: string[] = [];
    let push: ((payload: unknown) => void) | null = null;
    const progressA: string[] = [];
    const progressB: string[] = [];
    const host = new DesktopPresentationHost({
      sessions: {
        createInteractive: vi.fn().mockResolvedValue({
          session_id: "session-1",
          subscription_id: "sub-1",
        }),
      },
      interaction: {
        subscribe: vi.fn((subscriptionId: string, handler: (payload: unknown) => void) => {
          subscribedIds.push(subscriptionId);
          push = handler;
          return () => {
            push = null;
          };
        }),
        submit: vi.fn(async () => {
          push?.({
            method: "runtime.event",
            params: {
              subscription_id: "sub-1",
              session_id: "session-1",
              event: { type: "assistant-output-increment" },
            },
          });
          return {
            accepted: true,
            subscription_id: "sub-1",
            session_id: "session-1",
            termination_reason: "natural-completion",
            turns_taken: 1,
          };
        }),
      },
    } as never);

    const unsubscribeA = host.subscribeProgress("session-1", (event) => {
      progressA.push(event.type);
    });
    const unsubscribeB = host.subscribeProgress("session-2", (event) => {
      progressB.push(event.type);
    });

    await host.submit("session-1", "hello");

    expect(subscribedIds).toEqual(["sub-1"]);
    expect(progressA).toEqual(["assistant-output-increment", "run-terminated"]);
    expect(progressB).toEqual([]);
    unsubscribeA();
    unsubscribeB();
  });
});
