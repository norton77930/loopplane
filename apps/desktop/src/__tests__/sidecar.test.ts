import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

import type { AcceptedRun } from "../global";
import type { DesktopApi } from "../sidecar";
import { SidecarTransport } from "../sidecar";

function fakeApi(): {
  api: DesktopApi;
  submits: Array<{ subscriptionId: string; prompt: string }>;
  approvals: Array<{ requestId: string; allow: boolean }>;
  questions: Array<{ requestId: string; answers: string[] }>;
  push: (payload: unknown) => void;
} {
  const submits: Array<{ subscriptionId: string; prompt: string }> = [];
  const approvals: Array<{ requestId: string; allow: boolean }> = [];
  const questions: Array<{ requestId: string; answers: string[] }> = [];
  let pushHandler: ((payload: unknown) => void) | null = null;

  const api: DesktopApi = {
    app: {
      status: async () => ({ ready: true }),
      shutdown: async () => ({ ok: true }),
      subscribeStatus: () => () => undefined,
    },
    sessions: {
      list: async () => ({
        sessions: [{ session_id: "sess-1", title: "One", starred: false }],
      }),
      history: async () => ({ entries: [] }),
      rename: async () => ({}),
      setStarred: async () => ({}),
      delete: async () => ({}),
      fork: async () => ({ session_id: "sess-fork" }),
      createInteractive: async () => ({
        session_id: "sess-1",
        subscription_id: "sub-1",
      }),
      resumeInteractive: async () => ({
        session_id: "sess-1",
        subscription_id: "sub-2",
      }),
      releaseInteractive: async () => ({ released: true }),
    },
    projects: {
      list: async () => ({ projects: [{ id: "p1", label: "Work", session_ids: [] }] }),
      create: async () => ({ project: { id: "p2", label: "New" } }),
      rename: async () => ({}),
      remove: async () => ({}),
      assignSession: async () => ({}),
    },
    workspaces: {
      list: async () => ({
        workspaces: [
          { id: "w1", label: "Docs", availability: "available", actions: [] },
        ],
      }),
      chooseAndBind: async () => ({
        workspace: { id: "w2", label: "Bound", availability: "available" },
      }),
      chooseAndRelink: async () => ({}),
      remove: async () => ({}),
      revalidate: async () => ({}),
    },
    inspection: {
      get: async () => ({
        session_id: null,
        skills: [],
        tools: [],
        mcp: [],
        memory: [],
        unavailable: false,
      }),
    },
    agentControls: {
      get: async () => ({
        session_id: "s1",
        default_mode: null,
        selectable_modes: [],
        active_run: null,
        last_accepted_run: null,
        budget: {},
        actions: [],
        unavailable: false,
      }),
    },
    capabilities: {
      list: async () => ({ capabilities: [] }),
      invokeAction: async () => ({ capabilities: [] }),
    },
    interaction: {
      submit: async (subscriptionId, input) => {
        submits.push({ subscriptionId, prompt: input.prompt });
        pushHandler?.({
          method: "runtime.event",
          params: {
            event: {
              type: "assistant-output-increment",
              payload: { text: "hi", turn_index: 0 },
            },
          },
        });
        return {
          accepted: true,
          subscription_id: subscriptionId,
          session_id: "sess-1",
          termination_reason: "natural-completion",
          turns_taken: 1,
        };
      },
      cancel: async () => ({}),
      answerApproval: async (_sub, requestId, decision) => {
        approvals.push({ requestId, allow: decision.allow });
      },
      answerQuestion: async (_sub, requestId, answer) => {
        questions.push({ requestId, answers: answer.answers });
      },
      subscribe: (_subscriptionId, handler) => {
        pushHandler = handler;
        return () => {
          pushHandler = null;
        };
      },
    },
  };

  return {
    api,
    submits,
    approvals,
    questions,
    push: (payload) => pushHandler?.(payload),
  };
}

describe("SidecarTransport (typed Desktop API)", () => {
  it("creates interactive session, submits, and yields events without raw RPC ids", async () => {
    const { api, submits } = fakeApi();
    const transport = new SidecarTransport(api);
    const types: string[] = [];
    for await (const event of transport.run("hello")) {
      types.push(event.type);
    }
    expect(submits).toEqual([{ subscriptionId: "sub-1", prompt: "hello" }]);
    expect(types).toContain("assistant-output-increment");
    expect(types).toContain("run-terminated");
    expect(transport.activeSubscriptionId).toBe("sub-1");
    expect(transport.activeSessionId).toBe("sess-1");
  });

  it("does not synthesize a duplicate terminal event after the real one was yielded", async () => {
    const { api, push } = fakeApi();
    let resolveSubmit!: (
      value: AcceptedRun | PromiseLike<AcceptedRun>
    ) => void;
    api.interaction.submit = () =>
      new Promise<AcceptedRun>((resolve) => {
        resolveSubmit = resolve;
      });
    const transport = new SidecarTransport(api);
    const run = transport.run("hello");
    const first = run.next();
    await Promise.resolve();

    push({
      method: "runtime.event",
      params: {
        event: {
          type: "run-terminated",
          payload: { reason: "natural-completion", turns_taken: 1 },
        },
      },
    });
    await expect(first).resolves.toMatchObject({
      done: false,
      value: { type: "run-terminated" },
    });

    const completion = run.next();
    push({ method: "runtime.outcome", params: {} });
    resolveSubmit({
      termination_reason: "natural-completion",
      turns_taken: 1,
    });

    await expect(completion).resolves.toEqual({ done: true, value: undefined });
  });

  it("rejects and unsubscribes when submit fails without an outcome", async () => {
    const { api } = fakeApi();
    const unsubscribe = vi.fn();
    api.interaction.subscribe = () => unsubscribe;
    api.interaction.submit = async () => {
      throw new Error("runtime unavailable");
    };
    const transport = new SidecarTransport(api);
    const run = transport.run("hello");

    await expect(run.next()).rejects.toThrow("runtime unavailable");
    expect(unsubscribe).toHaveBeenCalledOnce();
  });

  it("lists sessions/projects/workspaces through typed methods", async () => {
    const { api } = fakeApi();
    const transport = new SidecarTransport(api);
    expect(await transport.listSessions()).toHaveLength(1);
    expect(await transport.listProjects()).toEqual([
      { id: "p1", label: "Work", session_ids: [] },
    ]);
    const workspaces = await transport.listWorkspaces();
    expect(workspaces[0]?.availability).toBe("available");
  });

  it("keeps drafts renderer-transient only", () => {
    const { api } = fakeApi();
    const transport = new SidecarTransport(api);
    transport.setDraft("unsent secret");
    expect(transport.draft).toBe("unsent secret");
    transport.clearDraft();
    expect(transport.draft).toBe("");
  });

  it("answers approvals and questions through typed methods", async () => {
    const { api, approvals, questions } = fakeApi();
    const transport = new SidecarTransport(api);
    for await (const _ of transport.run("x")) {
      /* drain */
    }
    transport.answerApproval("r1", true);
    transport.answerQuestion("r2", ["yes"]);
    await Promise.resolve();
    expect(approvals).toEqual([{ requestId: "r1", allow: true }]);
    expect(questions).toEqual([{ requestId: "r2", answers: ["yes"] }]);
  });

  it("does not place request or mutation ids on the public DesktopApi surface", () => {
    const src = readFileSync(
      fileURLToPath(new URL("../sidecar.ts", import.meta.url)),
      "utf8",
    );
    expect(src).not.toContain("jsonrpc");
    expect(src).not.toContain("mutation_id");
    expect(src).not.toContain("mutationId");
    expect(SidecarTransport.length).toBe(1);
  });
});
