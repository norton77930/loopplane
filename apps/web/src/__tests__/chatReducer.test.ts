import type { RawEvent } from "../api/types";
import { initialState, reduce } from "../state/chat";

const ev = (type: string, payload: unknown): RawEvent => ({ type, payload });

describe("artifact reference reducer", () => {
  it("preserves a current-session artifact reference on its tool entry", () => {
    let state = reduce(
      initialState,
      ev("tool-call-started", { call_id: "c1", tool_name: "report" }),
    );

    state = reduce(
      state,
      ev("tool-call-completed", {
        call_id: "c1",
        outcome: "success",
        artifact_reference: "artifact://session/report-1",
      }),
    );

    expect(state.entries).toEqual([
      {
        kind: "tool",
        callId: "c1",
        name: "report",
        outcome: "success",
        artifactReference: "artifact://session/report-1",
      },
    ]);
  });

  it("does not retain artifact references across a new session state", () => {
    let state = reduce(
      initialState,
      ev("tool-call-started", { call_id: "c1", tool_name: "report" }),
    );
    state = reduce(
      state,
      ev("tool-call-completed", {
        call_id: "c1",
        outcome: "success",
        artifact_reference: "artifact://session/report-1",
      }),
    );

    expect(state.entries).not.toEqual(initialState.entries);
    expect(initialState.entries).toEqual([]);
  });
});
