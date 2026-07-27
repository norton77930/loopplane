import { fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "../components/Composer";

describe("Composer", () => {
  it("integrates supporting controls and prompt into one input surface", () => {
    const { container } = render(
      <Composer
        disabled={false}
        onSend={() => undefined}
        extras={<span data-testid="composer-control">Model and attachments</span>}
      />,
    );

    const surface = container.querySelector(".composer-surface");
    expect(surface).toContainElement(screen.getByTestId("composer-control"));
    expect(surface).toContainElement(screen.getByLabelText("prompt"));
  });

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

  it("keeps editing available but blocks submit while supporting work is pending", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} sendDisabled onSend={onSend} />);
    const input = screen.getByLabelText("prompt");

    fireEvent.change(input, { target: { value: "wait for upload" } });
    expect(input).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    fireEvent.submit(input.closest("form")!);
    expect(onSend).not.toHaveBeenCalled();
  });
});
