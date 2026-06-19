import { fireEvent, render, screen } from "@testing-library/react";

import { Modal } from "../components/Modal";

describe("Modal", () => {
  it("renders an aria-modal dialog and closes on Escape and backdrop click", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal onClose={onClose} label="test dialog">
        <button>ok</button>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "test dialog");

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(container.querySelector(".modal-backdrop") as Element);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
