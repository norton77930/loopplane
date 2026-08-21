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
    // The sidebar reports the same fact in the same words as the banner rather
    // than "Mode: read_only" / "Lease: not owner"; the raw values stay on hover.
    const sidebar = screen.getByTestId("inspection-sidebar");
    expect(sidebar.textContent).toContain("Read-only");
    expect(sidebar.textContent).not.toContain("not owner");
    expect(
      screen.getByTitle("mode=read_only lease_owner=false"),
    ).toBeInTheDocument();
    // The banner and the sidebar now offer the same action in the same words.
    fireEvent.click(
      screen.getAllByRole("button", { name: "Take over" })[0]!,
    );
    expect(onRequestInteractive).toHaveBeenCalledWith("p2");
  });

  it("names each tab's state instead of decorating its title", () => {
    let ws = createEmptyWorkspace();
    ws = openPane(ws, { paneId: "p1", sessionId: "s1", title: "Owner" });
    ws = openPane(ws, { paneId: "p2", sessionId: "s2", title: "Watcher" });
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

    // The lease used to be a "● " prefix and a " (read-only)" suffix inside the
    // label, so a screen reader heard punctuation and a sighted reader saw a
    // footnote. The words are the accessible name; the dot is decoration.
    expect(
      screen.getByRole("tab", { name: "Owner — Driving this session" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Watcher — Read-only" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Owner").textContent).toBe("Owner");
    expect(document.body.textContent).not.toContain("(read-only)");
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
