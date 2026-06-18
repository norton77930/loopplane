import { fireEvent, render, screen } from "@testing-library/react";

import { ChatHeader } from "../components/ChatHeader";

describe("ChatHeader", () => {
  beforeEach(() => {
    // ThemeToggle (embedded) reads matchMedia on init.
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("shows the run status label", () => {
    render(<ChatHeader status="running" onStop={() => undefined} />);
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("offers Stop only while running and fires it", () => {
    const onStop = vi.fn();
    const { rerender } = render(<ChatHeader status="idle" onStop={onStop} />);
    expect(screen.queryByText("Stop")).not.toBeInTheDocument();
    rerender(<ChatHeader status="running" onStop={onStop} />);
    fireEvent.click(screen.getByText("Stop"));
    expect(onStop).toHaveBeenCalled();
  });
});
