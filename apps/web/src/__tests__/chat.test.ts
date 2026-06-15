import type { RawEvent } from "../api/types";
import { initialState, reduce, userPrompt } from "../state/chat";

const ev = (type: string, payload: unknown): RawEvent => ({ type, payload });

describe("reduce", () => {
  it("appends assistant output incrementally", () => {
    let state = userPrompt(initialState, "hello");
    state = reduce(state, ev("assistant-output-increment", { text: "Hel", turn_index: 0 }));
    state = reduce(state, ev("assistant-output-increment", { text: "lo", turn_index: 0 }));
    expect(state.turns).toEqual([
      { role: "user", text: "hello" },
      { role: "assistant", text: "Hello" },
    ]);
    expect(state.status).toBe("running");
  });

  it("records tool start then outcome in the timeline", () => {
    let state = reduce(
      initialState,
      ev("tool-call-started", { call_id: "c1", tool_name: "echo" }),
    );
    state = reduce(state, ev("tool-call-completed", { call_id: "c1", outcome: "success" }));
    expect(state.timeline).toEqual([
      { kind: "tool", callId: "c1", name: "echo", outcome: "success" },
    ]);
  });

  it("sets a pending approval and question", () => {
    let state = reduce(
      initialState,
      ev("approval-requested", { request_id: "r1", tool_name: "danger", input_summary: "x" }),
    );
    expect(state.pendingApproval).toEqual({ requestId: "r1", toolName: "danger" });
    state = reduce(state, ev("question-asked", { request_id: "r2", questions: [{ prompt: "ok?" }] }));
    expect(state.pendingQuestion).toEqual({ requestId: "r2", prompt: "ok?" });
  });

  it("marks termination on the timeline and status", () => {
    const state = reduce(
      initialState,
      ev("run-terminated", { reason: "natural-completion", turns_taken: 2 }),
    );
    expect(state.status).toBe("terminated");
    expect(state.timeline).toContainEqual({
      kind: "terminated",
      reason: "natural-completion",
      turns: 2,
    });
  });

  it("ignores unknown event types", () => {
    expect(reduce(initialState, ev("mystery", {}))).toBe(initialState);
  });
});
