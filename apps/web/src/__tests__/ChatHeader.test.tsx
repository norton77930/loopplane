import { fireEvent, render, screen } from "@testing-library/react";

import { ChatHeader } from "../components/ChatHeader";
import { ZERO_USAGE } from "../state/chat";

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
    render(<ChatHeader status="running" usage={{ total: ZERO_USAGE }} onStop={() => undefined} />);
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("offers Stop only while running and fires it", () => {
    const onStop = vi.fn();
    const { rerender } = render(
      <ChatHeader status="idle" usage={{ total: ZERO_USAGE }} onStop={onStop} />,
    );
    expect(screen.queryByText("Stop")).not.toBeInTheDocument();
    rerender(<ChatHeader status="running" usage={{ total: ZERO_USAGE }} onStop={onStop} />);
    fireEvent.click(screen.getByText("Stop"));
    expect(onStop).toHaveBeenCalled();
  });
});
