import type { RawEvent } from "../api/types";
import { errored, initialState, reduce, userPrompt } from "../state/chat";

const ev = (type: string, payload: unknown): RawEvent => ({ type, payload });

describe("reduce (ordered entries)", () => {
  it("records a user prompt and marks the run running", () => {
    const state = userPrompt(initialState, "hello");
    expect(state.entries).toEqual([{ kind: "user", text: "hello" }]);
    expect(state.status).toBe("running");
  });

  it("merges consecutive assistant increments into one entry", () => {
    let state = userPrompt(initialState, "hi");
    state = reduce(state, ev("assistant-output-increment", { text: "Hel", turn_index: 0 }));
    state = reduce(state, ev("assistant-output-increment", { text: "lo", turn_index: 0 }));
    expect(state.entries).toEqual([
      { kind: "user", text: "hi" },
      { kind: "assistant", text: "Hello" },
    ]);
  });

  it("interleaves tool cards between assistant messages in stream order", () => {
    let state = userPrompt(initialState, "do it");
    state = reduce(state, ev("assistant-output-increment", { text: "working", turn_index: 0 }));
    state = reduce(state, ev("tool-call-started", { call_id: "c1", tool_name: "echo" }));
    state = reduce(state, ev("tool-call-completed", { call_id: "c1", outcome: "success" }));
    state = reduce(state, ev("assistant-output-increment", { text: "done", turn_index: 1 }));
    expect(state.entries).toEqual([
      { kind: "user", text: "do it" },
      { kind: "assistant", text: "working" },
      { kind: "tool", callId: "c1", name: "echo", outcome: "success" },
      { kind: "assistant", text: "done" },
    ]);
  });

  it("marks a tool entry running until its matching completion", () => {
    let state = reduce(initialState, ev("tool-call-started", { call_id: "c1", tool_name: "echo" }));
    expect(state.entries).toEqual([{ kind: "tool", callId: "c1", name: "echo" }]);
    state = reduce(state, ev("tool-call-completed", { call_id: "c1", outcome: "failure" }));
    expect(state.entries).toEqual([
      { kind: "tool", callId: "c1", name: "echo", outcome: "failure" },
    ]);
  });

  it("ignores an orphan or duplicate tool-call-completed (no-op)", () => {
    const orphan = reduce(initialState, ev("tool-call-completed", { call_id: "x", outcome: "success" }));
    expect(orphan.entries).toEqual([]);

    let state = reduce(initialState, ev("tool-call-started", { call_id: "c1", tool_name: "echo" }));
    state = reduce(state, ev("tool-call-completed", { call_id: "c1", outcome: "success" }));
    const after = reduce(state, ev("tool-call-completed", { call_id: "c1", outcome: "failure" }));
    expect(after.entries).toEqual([
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

  it("appends a terminated marker, sets status, and clears pending dialogs", () => {
    let state = reduce(
      initialState,
      ev("approval-requested", { request_id: "r1", tool_name: "t", input_summary: "x" }),
    );
    state = reduce(state, ev("question-asked", { request_id: "r2", questions: [{ prompt: "ok?" }] }));
    state = reduce(state, ev("run-terminated", { reason: "natural-completion", turns_taken: 2 }));
    expect(state.status).toBe("terminated");
    expect(state.entries).toContainEqual({
      kind: "terminated",
      reason: "natural-completion",
      turns: 2,
    });
    expect(state.pendingApproval).toBeUndefined();
    expect(state.pendingQuestion).toBeUndefined();
  });

  it("ignores unknown event types", () => {
    expect(reduce(initialState, ev("mystery", {}))).toBe(initialState);
  });

  it("errored preserves entries and flips status", () => {
    const base = userPrompt(initialState, "hi");
    const state = errored(base);
    expect(state.status).toBe("error");
    expect(state.entries).toEqual(base.entries);
  });
});
