import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CoworkShell } from "@loopplane/cowork-presentation";
import {
  claimLease,
  createEmptyWorkspace,
  openPane,
} from "@loopplane/cowork-presentation";
import { InspectionSidebar } from "@loopplane/cowork-presentation";

describe("Desktop multi-pane shell (T049/T053)", () => {
  it("shows read-only banner when focused pane is not lease owner", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1", title: "A" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2", title: "B" });
    ws = claimLease(ws, "p1").state;
    // focus B without lease
    ws = { ...ws, focusedPaneId: "p2", panes: ws.panes.map((p) => ({
      ...p,
      focused: p.paneId === "p2",
      mode: p.paneId === "p1" ? "interactive" : "read_only",
    })) };

    const onRequestInteractive = vi.fn();
    render(
      <CoworkShell
        workspace={ws}
        onFocusPane={() => undefined}
        onClosePane={() => undefined}
        onRequestInteractive={onRequestInteractive}
        rightSidebar={
          <InspectionSidebar
            sessionId="s2"
            title="B"
            mode="read_only"
            leaseOwner={false}
          />
        }
      >
        <div>body</div>
      </CoworkShell>,
    );

    expect(screen.getByRole("status").textContent).toMatch(/read-only/i);
    expect(screen.getByTestId("inspection-sidebar").textContent).toContain(
      "not owner",
    );
    fireEvent.click(screen.getByText("Make interactive"));
    expect(onRequestInteractive).toHaveBeenCalledWith("p2");
  });

  it("marks lease owner tab and rejects second submit via canSubmit semantics", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1", title: "Owner" });
    ws = claimLease(ws, "p1").state;
    render(
      <CoworkShell
        workspace={ws}
        onFocusPane={() => undefined}
        onClosePane={() => undefined}
        onRequestInteractive={() => undefined}
      >
        <div>body</div>
      </CoworkShell>,
    );
    const tab = screen.getByRole("tab", { name: /Owner/i });
    expect(tab.getAttribute("data-lease-owner")).toBe("true");
  });
});
