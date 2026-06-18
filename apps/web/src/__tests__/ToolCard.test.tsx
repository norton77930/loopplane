import { fireEvent, render, screen } from "@testing-library/react";

import { ToolCard } from "../components/ToolCard";

describe("ToolCard", () => {
  it("shows a running status when there is no outcome yet", () => {
    render(<ToolCard entry={{ kind: "tool", callId: "c1", name: "echo" }} />);
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("shows success or failure when completed", () => {
    const { rerender } = render(
      <ToolCard entry={{ kind: "tool", callId: "c1", name: "echo", outcome: "success" }} />,
    );
    expect(screen.getByText("success")).toBeInTheDocument();
    rerender(<ToolCard entry={{ kind: "tool", callId: "c1", name: "echo", outcome: "failure" }} />);
    expect(screen.getByText("failure")).toBeInTheDocument();
  });

  it("toggles its collapsible detail", () => {
    const { container } = render(<ToolCard entry={{ kind: "tool", callId: "c1", name: "echo" }} />);
    expect(container.querySelector(".tool-detail")).toBeNull();
    fireEvent.click(screen.getByRole("button"));
    expect(container.querySelector(".tool-detail")).not.toBeNull();
  });
});
