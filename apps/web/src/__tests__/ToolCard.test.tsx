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

  it("offers metadata-only reference attachment without raw open actions", () => {
    const onAttachReference = vi.fn();
    render(
      <ToolCard
        entry={{
          kind: "tool",
          callId: "c1",
          name: "report",
          outcome: "success",
          artifactReference: "artifact://session/report-1",
        }}
        onAttachReference={onAttachReference}
      />,
    );

    expect(screen.getByText("artifact://session/report-1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open|download|execute/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Attach reference" }));
    expect(onAttachReference).toHaveBeenCalledWith("artifact://session/report-1");
  });

  it("toggles its collapsible detail", () => {
    const { container } = render(<ToolCard entry={{ kind: "tool", callId: "c1", name: "echo" }} />);
    expect(container.querySelector(".tool-detail")).toBeNull();
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-controls");
    fireEvent.click(toggle);
    expect(screen.getByRole("region", { name: "echo tool details" })).toBeInTheDocument();
  });
});
