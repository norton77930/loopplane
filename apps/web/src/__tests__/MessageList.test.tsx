import { fireEvent, render, screen } from "@testing-library/react";

import { MessageList } from "../components/MessageList";

describe("MessageList", () => {
  it("renders entries in stream order: user, assistant markdown, tool, terminated", () => {
    render(
      <MessageList
        entries={[
          { kind: "user", text: "hello" },
          { kind: "assistant", text: "**hi**" },
          { kind: "tool", callId: "c1", name: "echo", outcome: "success" },
          { kind: "terminated", reason: "natural-completion", turns: 1 },
        ]}
      />,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("hi").tagName).toBe("STRONG"); // assistant rendered as markdown
    expect(screen.getByText("echo")).toBeInTheDocument(); // tool card
    expect(screen.getByText(/natural-completion/)).toBeInTheDocument(); // terminal marker
  });

  it("offers jump-to-latest only when scrolled up", () => {
    render(<MessageList entries={[{ kind: "assistant", text: "hi" }]} />);
    const region = screen.getByTestId("messages");
    expect(screen.queryByText("Jump to latest")).not.toBeInTheDocument();

    // Simulate a scrolled-up viewport (jsdom does not lay out scrolling).
    Object.defineProperty(region, "scrollHeight", { value: 1000, configurable: true });
    Object.defineProperty(region, "clientHeight", { value: 300, configurable: true });
    Object.defineProperty(region, "scrollTop", { value: 0, writable: true, configurable: true });
    fireEvent.scroll(region);

    expect(screen.getByText("Jump to latest")).toBeInTheDocument();
  });

  it("copies a message's text via the copy action", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    render(<MessageList entries={[{ kind: "user", text: "hello world" }]} />);
    fireEvent.click(screen.getByText("Copy"));
    expect(writeText).toHaveBeenCalledWith("hello world");
  });

  it("offers Regenerate on the latest assistant message and invokes the handler", () => {
    const onRegenerate = vi.fn();
    render(
      <MessageList
        entries={[
          { kind: "user", text: "go" },
          { kind: "assistant", text: "answer" },
        ]}
        onRegenerate={onRegenerate}
        canRegenerate
      />,
    );
    fireEvent.click(screen.getByText("Regenerate"));
    expect(onRegenerate).toHaveBeenCalled();
  });

  it("disables Regenerate while a run is in flight", () => {
    render(
      <MessageList
        entries={[{ kind: "assistant", text: "answer" }]}
        onRegenerate={() => undefined}
        canRegenerate={false}
      />,
    );
    expect(screen.getByText("Regenerate")).toBeDisabled();
  });
});
