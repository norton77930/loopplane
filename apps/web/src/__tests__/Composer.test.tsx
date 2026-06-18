import { fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "../components/Composer";

describe("Composer", () => {
  it("disables the input and Send while a run is in flight", () => {
    render(<Composer disabled onSend={() => undefined} />);
    expect(screen.getByLabelText("prompt")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("emits trimmed, non-empty text and clears the field", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);
    const input = screen.getByLabelText("prompt") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "  hello  " } });
    fireEvent.submit(input.closest("form")!);
    expect(onSend).toHaveBeenCalledWith("hello");
    expect(input.value).toBe("");
  });

  it("ignores an empty or whitespace-only prompt", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);
    const input = screen.getByLabelText("prompt");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(input.closest("form")!);
    expect(onSend).not.toHaveBeenCalled();
  });
});
