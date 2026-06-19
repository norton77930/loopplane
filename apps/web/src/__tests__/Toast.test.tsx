import { act, fireEvent, render, screen } from "@testing-library/react";

import { ToastProvider, useToast } from "../components/Toast";

function Probe() {
  const { notify } = useToast();
  return (
    <button type="button" onClick={() => notify("Saved!")}>
      go
    </button>
  );
}

describe("Toast", () => {
  it("shows a toast and auto-dismisses it", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <Probe />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("go"));
      expect(screen.getByText("Saved!")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("notify is a safe no-op when there is no provider", () => {
    function Bare() {
      const { notify } = useToast();
      notify("ignored");
      return <span>ok</span>;
    }
    expect(() => render(<Bare />)).not.toThrow();
  });
});
