import { fireEvent, render, screen } from "@testing-library/react";

import { ApprovalDialog } from "../components/ApprovalDialog";

describe("ApprovalDialog", () => {
  it("emits allow-once, deny, and always-allow-this-session", () => {
    const onDecide = vi.fn();
    render(<ApprovalDialog toolName="danger" onDecide={onDecide} />);

    fireEvent.click(screen.getByText("Allow"));
    expect(onDecide).toHaveBeenCalledWith({ allow: true, scope: "once" });

    fireEvent.click(screen.getByText("Deny"));
    expect(onDecide).toHaveBeenCalledWith({ allow: false });

    fireEvent.click(screen.getByText("Always allow this session"));
    expect(onDecide).toHaveBeenCalledWith({ allow: true, scope: "session" });
  });
});
