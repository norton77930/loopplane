import { fireEvent, render, screen } from "@testing-library/react";

import { QuestionDialog } from "../components/QuestionDialog";

describe("QuestionDialog", () => {
  it("submits a single selected option", () => {
    const onAnswer = vi.fn();
    render(<QuestionDialog prompt="Pick one" options={["A", "B"]} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "A" }));
    fireEvent.click(screen.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith(["A"]);
  });

  it("submits multiple selected options together", () => {
    const onAnswer = vi.fn();
    render(<QuestionDialog prompt="Pick some" options={["A", "B", "C"]} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "A" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "C" }));
    fireEvent.click(screen.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith(["A", "C"]);
  });

  it("falls back to a free-text field when there are no options", () => {
    const onAnswer = vi.fn();
    render(<QuestionDialog prompt="Why?" options={[]} onAnswer={onAnswer} />);
    fireEvent.change(screen.getByLabelText("answer"), { target: { value: "because" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith(["because"]);
  });

  it("dismisses without answering on Escape or backdrop click", () => {
    const onAnswer = vi.fn();
    const onClose = vi.fn();
    const view = render(
      <QuestionDialog
        prompt="Pick one"
        options={["A", "B"]}
        onAnswer={onAnswer}
        onClose={onClose}
      />,
    );

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    expect(onAnswer).not.toHaveBeenCalled();

    view.rerender(
      <QuestionDialog
        prompt="Pick one"
        options={["A", "B"]}
        onAnswer={onAnswer}
        onClose={onClose}
      />,
    );
    const backdrop = screen.getByRole("dialog").parentElement;
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop as HTMLElement);

    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("does not answer an option question until at least one option is selected", () => {
    const onAnswer = vi.fn();
    render(<QuestionDialog prompt="Pick one" options={["A", "B"]} onAnswer={onAnswer} />);

    fireEvent.click(screen.getByText("Send"));

    expect(onAnswer).not.toHaveBeenCalled();
  });
});
