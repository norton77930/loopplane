import { fireEvent, render, screen } from "@testing-library/react";

import { SessionList } from "../components/SessionList";

describe("SessionList", () => {
  it("lists sessions and opens one", () => {
    const onOpen = vi.fn();
    render(
      <SessionList
        sessions={[{ session_id: "s1", last_active_at: "2026-01-01" }]}
        onOpen={onOpen}
      />,
    );
    expect(screen.getByText("s1")).toBeInTheDocument();
    fireEvent.click(screen.getByText("s1"));
    expect(onOpen).toHaveBeenCalledWith("s1");
  });

  it("shows an empty state", () => {
    render(<SessionList sessions={[]} onOpen={() => undefined} />);
    expect(screen.getByText(/No sessions/)).toBeInTheDocument();
  });
});
