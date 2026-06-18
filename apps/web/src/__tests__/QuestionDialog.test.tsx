import { fireEvent, render, screen } from "@testing-library/react";

import { QuestionDialog } from "../components/QuestionDialog";

describe("QuestionDialog", () => {
  it("submits a single free-text answer", () => {
    const onAnswer = vi.fn();
    render(<QuestionDialog prompt="ok?" onAnswer={onAnswer} />);
    fireEvent.change(screen.getByLabelText("answer"), { target: { value: "yes" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith("yes");
  });
});
