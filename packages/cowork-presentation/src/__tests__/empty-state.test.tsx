import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageList } from "../components/MessageList";

describe("MessageList empty state", () => {
  it("keeps Web's starter prompts when the host asks for nothing else", () => {
    render(<MessageList entries={[]} onExample={() => undefined} />);

    expect(screen.getByText("Summarize the attached file")).toBeInTheDocument();
    expect(screen.getByText(/attach a file/i)).toBeInTheDocument();
  });

  it("lets a host replace the prompts and the hint", () => {
    render(
      <MessageList
        entries={[]}
        onExample={() => undefined}
        examples={["What does this project do?", "List the tools you can use"]}
        emptyHint="Ask about loopplane, or choose a starting point."
      />,
    );

    expect(screen.getByText("What does this project do?")).toBeInTheDocument();
    // A host without an attach control must not advertise one.
    expect(screen.queryByText(/attach a file/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Summarize the attached file"),
    ).not.toBeInTheDocument();
  });

  it("runs the host's handler when a prompt is chosen", () => {
    const onExample = vi.fn();
    render(
      <MessageList entries={[]} onExample={onExample} examples={["Pick me"]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pick me" }));

    expect(onExample).toHaveBeenCalledWith("Pick me");
  });

  it("shows no prompts at all when the host wired no handler", () => {
    // Desktop shipped exactly this: three chips rendered, `onExample` undefined,
    // so every click ran `onExample?.(…)` and did nothing.
    render(<MessageList entries={[]} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
