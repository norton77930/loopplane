import { describe, expect, it } from "vitest";

import {
  canSubmitFromPane,
  claimLease,
  closePane,
  createEmptyWorkspace,
  focusPane,
  openPane,
  releaseLease,
  setPaneDraft,
} from "../panes/state";

describe("pane workspace state (T049/T051)", () => {
  it("opens panes and deduplicates by session id", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1", title: "One" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2", title: "Two" });
    expect(ws.order).toEqual(["p1", "p2"]);
    // Same session focuses existing pane
    ws = openPane(ws, { paneId: "p3", sessionId: "s1", title: "Dup" });
    expect(ws.order).toEqual(["p1", "p2"]);
    expect(ws.focusedPaneId).toBe("p1");
  });

  it("keeps drafts pane-local", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2" });
    ws = setPaneDraft(ws, "p1", "draft-a");
    ws = setPaneDraft(ws, "p2", "draft-b");
    expect(ws.panes.find((p) => p.paneId === "p1")?.draft.text).toBe("draft-a");
    expect(ws.panes.find((p) => p.paneId === "p2")?.draft.text).toBe("draft-b");
  });

  it("allows only one interactive lease owner", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2" });
    const claimA = claimLease(ws, "p1");
    expect(claimA.ok).toBe(true);
    ws = claimA.state;
    expect(canSubmitFromPane(ws, "p1")).toBe(true);
    expect(canSubmitFromPane(ws, "p2")).toBe(false);
    const claimB = claimLease(ws, "p2");
    expect(claimB.ok).toBe(false);
    expect(claimB.ownerPaneId).toBe("p1");
    // Focus non-owner remains read-only
    ws = focusPane(ws, "p2");
    expect(ws.panes.find((p) => p.paneId === "p2")?.mode).toBe("read_only");
    ws = releaseLease(ws, "p1");
    expect(ws.leaseOwnerPaneId).toBeNull();
    const claimB2 = claimLease(ws, "p2");
    expect(claimB2.ok).toBe(true);
  });

  it("closing owner releases lease", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2" });
    ws = claimLease(ws, "p1").state;
    ws = closePane(ws, "p1");
    expect(ws.leaseOwnerPaneId).toBeNull();
    expect(ws.focusedPaneId).toBe("p2");
    expect(ws.order).toEqual(["p2"]);
  });
});
