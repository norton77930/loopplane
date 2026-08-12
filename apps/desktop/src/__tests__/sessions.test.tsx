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
});
