import { fireEvent, render, screen } from "@testing-library/react";

import { Sidebar } from "../components/Sidebar";

describe("Sidebar", () => {
  it("shows an empty state and a new-chat affordance", () => {
    const onNew = vi.fn();
    render(<Sidebar sessions={[]} activeId={null} onOpen={() => undefined} onNew={onNew} />);
    expect(screen.getByText("No sessions yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("+ New chat"));
    expect(onNew).toHaveBeenCalled();
  });

  it("lists sessions with recency and opens one", () => {
    const onOpen = vi.fn();
    render(
      <Sidebar
        sessions={[{ session_id: "s1", last_active_at: "2026-06-19T10:00:00Z" }]}
        activeId={null}
        onOpen={onOpen}
        onNew={() => undefined}
      />,
    );
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("2026-06-19T10:00:00Z")).toBeInTheDocument();
    fireEvent.click(screen.getByText("s1"));
    expect(onOpen).toHaveBeenCalledWith("s1");
  });
});
