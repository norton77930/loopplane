import { fireEvent, render } from "@testing-library/react";

import { useFocusTrap } from "../hooks/useFocusTrap";

function Trapped({ onClose }: { onClose: () => void }) {
  const ref = useFocusTrap<HTMLDivElement>(onClose);
  return (
    <div>
      <button>outside</button>
      <div ref={ref}>
        <button>first</button>
        <button>last</button>
      </div>
    </div>
  );
}

describe("useFocusTrap", () => {
  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    const { getByText } = render(<Trapped onClose={onClose} />);
    fireEvent.keyDown(getByText("first"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("focuses the first focusable on mount and restores focus on unmount", () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();

    const { getByText, unmount } = render(<Trapped onClose={() => undefined} />);
    expect(document.activeElement).toBe(getByText("first"));

    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("wraps Tab from the last focusable back to the first", () => {
    const { getByText } = render(<Trapped onClose={() => undefined} />);
    getByText("last").focus();
    fireEvent.keyDown(getByText("last"), { key: "Tab" });
    expect(document.activeElement).toBe(getByText("first"));
  });
});
