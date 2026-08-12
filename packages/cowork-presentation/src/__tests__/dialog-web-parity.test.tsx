import { fireEvent, render, screen } from "@testing-library/react";

import { ApprovalDialog } from "../components/ApprovalDialog";

describe("shared dialog Web parity", () => {
  it("maps backdrop dismissal to the explicit safe approval denial", () => {
    const onDecide = vi.fn();
    render(<ApprovalDialog toolName="danger" onDecide={onDecide} />);

    const backdrop = screen.getByRole("dialog").parentElement;
    expect(backdrop).toHaveClass("modal-backdrop");
    fireEvent.click(backdrop as HTMLElement);

    expect(onDecide).toHaveBeenCalledOnce();
    expect(onDecide).toHaveBeenCalledWith({ allow: false });
  });
});
