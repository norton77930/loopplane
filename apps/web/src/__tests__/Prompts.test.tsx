import { fireEvent, render, screen } from "@testing-library/react";

import { Prompts } from "../components/Prompts";
import { initialState } from "../state/chat";

describe("Prompts", () => {
  it("renders a pending approval and calls the handler", () => {
    const onApproval = vi.fn();
    render(
      <Prompts
        state={{ ...initialState, pendingApproval: { requestId: "r1", toolName: "danger" } }}
        onApproval={onApproval}
        onQuestion={() => undefined}
      />,
    );
    expect(screen.getByText(/Approve tool danger/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Allow"));
    expect(onApproval).toHaveBeenCalledWith("r1", true);
  });

  it("renders a pending question and submits the answer", () => {
    const onQuestion = vi.fn();
    render(
      <Prompts
        state={{ ...initialState, pendingQuestion: { requestId: "r2", prompt: "ok?" } }}
        onApproval={() => undefined}
        onQuestion={onQuestion}
      />,
    );
    fireEvent.change(screen.getByLabelText("answer"), { target: { value: "yes" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onQuestion).toHaveBeenCalledWith("r2", "yes");
  });
});
