import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SessionSidebar } from "../components/SessionSidebar";

describe("SessionSidebar (T038/T045)", () => {
  it("renders sessions projects workspaces and fires actions", () => {
    const onSelectSession = vi.fn();
    const onToggleStar = vi.fn();
    const onDeleteSession = vi.fn();
    const onRemoveProject = vi.fn();
    const onRelinkWorkspace = vi.fn();

    render(
      <SessionSidebar
        sessions={[
          { session_id: "s1", title: "First", starred: true },
          { session_id: "s2", title: "Second", starred: false },
        ]}
        projects={[{ id: "p1", label: "Alpha", session_ids: ["s1"] }]}
        workspaces={[
          {
            id: "w1",
            label: "Docs",
            availability: "relink_required",
            actions: ["relink"],
          },
        ]}
        activeSessionId="s1"
        selectedWorkspaceId="w1"
        onSelectSession={onSelectSession}
        onNewSession={() => undefined}
        onToggleStar={onToggleStar}
        onDeleteSession={onDeleteSession}
        onForkSession={() => undefined}
        onCreateProject={() => undefined}
        onRemoveProject={onRemoveProject}
        onBindWorkspace={() => undefined}
        onRelinkWorkspace={onRelinkWorkspace}
        onSelectWorkspace={() => undefined}
      />,
    );

    expect(screen.getByTestId("session-list").textContent).toContain("First");
    expect(screen.getByTestId("project-list").textContent).toContain("Alpha");
    expect(screen.getByText(/Removing a project ungroups/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Second"));
    expect(onSelectSession).toHaveBeenCalledWith("s2");

    fireEvent.click(screen.getByLabelText("Unstar session"));
    expect(onToggleStar).toHaveBeenCalledWith("s1", false);

    fireEvent.click(screen.getAllByLabelText("Delete session")[0]!);
    expect(onDeleteSession).toHaveBeenCalledWith("s1");

    fireEvent.click(screen.getByLabelText("Remove project Alpha"));
    expect(onRemoveProject).toHaveBeenCalledWith("p1");

    fireEvent.click(screen.getByText("Relink…"));
    expect(onRelinkWorkspace).toHaveBeenCalledWith("w1");
  });

  it("does not render absolute paths", () => {
    const { container } = render(
      <SessionSidebar
        sessions={[]}
        projects={[]}
        workspaces={[
          { id: "w1", label: "Docs", availability: "available", actions: [] },
        ]}
        onSelectSession={() => undefined}
        onNewSession={() => undefined}
        onToggleStar={() => undefined}
        onDeleteSession={() => undefined}
        onForkSession={() => undefined}
        onCreateProject={() => undefined}
        onRemoveProject={() => undefined}
        onBindWorkspace={() => undefined}
        onRelinkWorkspace={() => undefined}
        onSelectWorkspace={() => undefined}
      />,
    );
    expect(container.textContent).not.toMatch(/[A-Za-z]:\\/);
    expect(container.textContent).not.toContain("/Users/");
    expect(container.textContent).not.toContain("C:\\");
  });

  function sidebar(props: Partial<Parameters<typeof SessionSidebar>[0]> = {}) {
    return render(
      <SessionSidebar
        sessions={[
          { session_id: "s1", title: "Fix the CI failure", starred: true },
          { session_id: "s2", title: "Explain the gateway", starred: false },
          { session_id: "s3", title: "Read the audit log", starred: false },
        ]}
        projects={[]}
        workspaces={[
          { id: "w1", label: "loopplane", availability: "available", actions: [] },
        ]}
        selectedWorkspaceId="w1"
        onSelectSession={() => undefined}
        onNewSession={() => undefined}
        onToggleStar={() => undefined}
        onDeleteSession={() => undefined}
        onForkSession={() => undefined}
        onCreateProject={() => undefined}
        onRemoveProject={() => undefined}
        onBindWorkspace={() => undefined}
        onRelinkWorkspace={() => undefined}
        onSelectWorkspace={() => undefined}
        {...props}
      />,
    );
  }

  it("puts starred sessions above the rest under their own heading", () => {
    sidebar();

    const list = screen.getByTestId("session-list");
    const text = list.textContent ?? "";
    expect(text.indexOf("Starred")).toBeLessThan(text.indexOf("All sessions"));
    expect(text.indexOf("Fix the CI failure")).toBeLessThan(
      text.indexOf("Explain the gateway"),
    );
  });

  it("keeps the group headings inside the one labelled list", () => {
    // `Find-UniqueElement` in the packaged smoke fails unless exactly one list
    // carries this name, so headings are rows rather than separate lists.
    sidebar();

    expect(
      screen.getAllByRole("list", { name: "LoopPlane smoke session list" }),
    ).toHaveLength(1);
  });

  it("filters the list as the user types", () => {
    sidebar();

    fireEvent.change(screen.getByLabelText("Search sessions"), {
      target: { value: "audit" },
    });

    const list = screen.getByTestId("session-list");
    expect(list.textContent).toContain("Read the audit log");
    expect(list.textContent).not.toContain("Explain the gateway");
  });

  it("says so when a search matches nothing", () => {
    sidebar();

    fireEvent.change(screen.getByLabelText("Search sessions"), {
      target: { value: "nothing here" },
    });

    expect(screen.getByText("No sessions match")).toBeInTheDocument();
  });

  it("keeps the bound folder and its settings in the footer", () => {
    const onOpenSettings = vi.fn();
    sidebar({ onOpenSettings });

    expect(screen.getByText("⌂ loopplane")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Settings"));
    expect(onOpenSettings).toHaveBeenCalled();
  });

  it("names the workspace state in words rather than the enum", () => {
    sidebar({
      workspaces: [
        { id: "w1", label: "loopplane", availability: "relink_required", actions: [] },
      ],
    });

    expect(screen.getByText("Folder moved")).toBeInTheDocument();
    expect(screen.queryByText("relink_required")).not.toBeInTheDocument();
  });
});
