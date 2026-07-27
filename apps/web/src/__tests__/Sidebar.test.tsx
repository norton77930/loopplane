import { fireEvent, render, screen } from "@testing-library/react";

import type { SessionSummary } from "../api/types";
import { Sidebar } from "../components/Sidebar";

const session = (over: Partial<SessionSummary> = {}): SessionSummary => ({
  session_id: "s1",
  label: null,
  last_active_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  ...over,
});

describe("Sidebar", () => {
  it("exposes session navigation and a clearly named primary action", () => {
    render(
      <Sidebar sessions={[]} activeId={null} onOpen={() => undefined} onNew={() => undefined} />,
    );

    expect(screen.getByRole("navigation", { name: "Sessions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New chat" })).toBeInTheDocument();
  });

  it("shows an empty state and a new-chat affordance", () => {
    const onNew = vi.fn();
    render(
      <Sidebar sessions={[]} activeId={null} onOpen={() => undefined} onNew={onNew} />,
    );
    expect(screen.getByText("No sessions yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("New chat"));
    expect(onNew).toHaveBeenCalled();
  });

  it("shows a title (label, with a short-id fallback), grouped by recency", () => {
    const onOpen = vi.fn();
    render(
      <Sidebar
        sessions={[
          session({ session_id: "abcdef123456", label: "My Chat" }),
          session({ session_id: "raw1", label: null }),
        ]}
        activeId={null}
        onOpen={onOpen}
        onNew={() => undefined}
      />,
    );
    expect(screen.getByText("My Chat")).toBeInTheDocument(); // label as title
    expect(screen.getByText("raw1")).toBeInTheDocument(); // short-id fallback
    expect(screen.getByText("Today")).toBeInTheDocument(); // recency group
    fireEvent.click(screen.getByText("My Chat"));
    expect(onOpen).toHaveBeenCalledWith("abcdef123456");
  });

  it("renames a session via the overflow menu (Enter saves)", () => {
    const onRename = vi.fn();
    render(
      <Sidebar
        sessions={[session({ label: "Old" })]}
        activeId={null}
        onOpen={() => undefined}
        onNew={() => undefined}
        onRename={onRename}
      />,
    );
    fireEvent.click(screen.getByLabelText("session menu"));
    fireEvent.click(screen.getByText("Rename"));
    const input = screen.getByLabelText("rename session");
    fireEvent.change(input, { target: { value: "New Name" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onRename).toHaveBeenCalledWith("s1", "New Name");
  });

  it("deletes a session via the overflow menu after a confirm", () => {
    const onDelete = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <Sidebar
        sessions={[session()]}
        activeId={null}
        onOpen={() => undefined}
        onNew={() => undefined}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByLabelText("session menu"));
    fireEvent.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith("s1");
    confirm.mockRestore();
  });
});
