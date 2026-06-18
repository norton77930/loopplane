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

  it("merges reasoning increments into a reasoning entry, separate from and before the answer", () => {
    let state = userPrompt(initialState, "q");
    state = reduce(state, ev("assistant-reasoning-increment", { text: "let me ", turn_index: 0 }));
    state = reduce(state, ev("assistant-reasoning-increment", { text: "think", turn_index: 0 }));
    state = reduce(state, ev("assistant-output-increment", { text: "answer", turn_index: 0 }));
    expect(state.entries).toEqual([
      { kind: "user", text: "q" },
      { kind: "reasoning", text: "let me think" },
      { kind: "assistant", text: "answer" },
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

  it("sets a pending approval and maps a question's text + options", () => {
    let state = reduce(
      initialState,
      ev("approval-requested", { request_id: "r1", tool_name: "danger", input_summary: "x" }),
    );
    expect(state.pendingApproval).toEqual({ requestId: "r1", toolName: "danger" });
    state = reduce(
      state,
      ev("question-asked", { request_id: "r2", questions: [{ text: "ok?", options: ["yes", "no"] }] }),
    );
    expect(state.pendingQuestion).toEqual({ requestId: "r2", prompt: "ok?", options: ["yes", "no"] });
  });

  it("maps a question with no options to an empty options list (free-text fallback)", () => {
    const state = reduce(
      initialState,
      ev("question-asked", { request_id: "r3", questions: [{ text: "why?", options: [] }] }),
    );
    expect(state.pendingQuestion).toEqual({ requestId: "r3", prompt: "why?", options: [] });
  });

  it("accumulates per-turn and session token usage on turn-completed", () => {
    let state = reduce(
      initialState,
      ev("turn-completed", {
        turn_index: 0,
        stop_reason: "end-turn",
        usage: { input_tokens: 10, output_tokens: 5, cached_tokens: 1, reasoning_tokens: 2 },
      }),
    );
    expect(state.usage.last).toEqual({ input_tokens: 10, output_tokens: 5, cached_tokens: 1, reasoning_tokens: 2 });
    expect(state.usage.total).toEqual({ input_tokens: 10, output_tokens: 5, cached_tokens: 1, reasoning_tokens: 2 });
    state = reduce(
      state,
      ev("turn-completed", {
        turn_index: 1,
        stop_reason: "end-turn",
        usage: { input_tokens: 4, output_tokens: 6, cached_tokens: 0, reasoning_tokens: 0 },
      }),
    );
    expect(state.usage.last).toEqual({ input_tokens: 4, output_tokens: 6, cached_tokens: 0, reasoning_tokens: 0 });
    expect(state.usage.total).toEqual({ input_tokens: 14, output_tokens: 11, cached_tokens: 1, reasoning_tokens: 2 });
  });

  it("appends a terminated marker, sets status, and clears pending dialogs", () => {
    let state = reduce(
      initialState,
      ev("approval-requested", { request_id: "r1", tool_name: "t", input_summary: "x" }),
    );
    state = reduce(state, ev("question-asked", { request_id: "r2", questions: [{ text: "ok?", options: [] }] }));
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
