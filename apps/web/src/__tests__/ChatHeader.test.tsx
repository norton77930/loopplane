import { fireEvent, render, screen } from "@testing-library/react";

import { ChatHeader } from "../components/ChatHeader";
import { ZERO_USAGE } from "../state/chat";

const noop = () => undefined;

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
    render(
      <ChatHeader
        status="running"
        usage={{ total: ZERO_USAGE }}
        onStop={noop}
        inspectOpen={false}
        onToggleInspect={noop}
      />,
    );
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("offers Stop only while running and fires it", () => {
    const onStop = vi.fn();
    const { rerender } = render(
      <ChatHeader
        status="idle"
        usage={{ total: ZERO_USAGE }}
        onStop={onStop}
        inspectOpen={false}
        onToggleInspect={noop}
      />,
    );
    expect(screen.queryByText("Stop")).not.toBeInTheDocument();
    rerender(
      <ChatHeader
        status="running"
        usage={{ total: ZERO_USAGE }}
        onStop={onStop}
        inspectOpen={false}
        onToggleInspect={noop}
      />,
    );
    fireEvent.click(screen.getByText("Stop"));
    expect(onStop).toHaveBeenCalled();
  });

  it("toggles the inspection panel", () => {
    const onToggleInspect = vi.fn();
    render(
      <ChatHeader
        status="idle"
        usage={{ total: ZERO_USAGE }}
        onStop={noop}
        inspectOpen={false}
        onToggleInspect={onToggleInspect}
      />,
    );
    fireEvent.click(screen.getByText("Inspect"));
    expect(onToggleInspect).toHaveBeenCalled();
  });
});
