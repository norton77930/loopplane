import { fireEvent, render, screen } from "@testing-library/react";

import type { SessionSummary } from "../api/types";
import { Sidebar } from "../components/Sidebar";

const session = (over: Partial<SessionSummary> = {}): SessionSummary => ({
  session_id: "s1",
  label: "Alpha",
  last_active_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  starred: false,
  ...over,
});

describe("Sidebar session parity controls", () => {
  it("toggles star state, searches sessions, and bulk deletes selected rows", () => {
    const onToggleStar = vi.fn();
    const onSearch = vi.fn();
    const onBulkDelete = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <Sidebar
        sessions={[
          session({ session_id: "s1", label: "Alpha", starred: false }),
          session({ session_id: "s2", label: "Beta", starred: true }),
        ]}
        activeId={null}
        onOpen={() => undefined}
        onNew={() => undefined}
        onToggleStar={onToggleStar}
        onSearch={onSearch}
        onBulkDelete={onBulkDelete}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "star session Alpha" }));
    expect(onToggleStar).toHaveBeenCalledWith("s1", true);

    fireEvent.change(screen.getByLabelText("search sessions"), {
      target: { value: "beta" },
    });
    expect(onSearch).toHaveBeenCalledWith("beta");

    fireEvent.click(screen.getByLabelText("select Alpha"));
    fireEvent.click(screen.getByLabelText("select Beta"));
    fireEvent.click(screen.getByRole("button", { name: "Delete selected" }));
    expect(onBulkDelete).toHaveBeenCalledWith(["s1", "s2"]);

    confirm.mockRestore();
  });
});
