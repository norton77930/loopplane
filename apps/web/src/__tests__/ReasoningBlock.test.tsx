import { fireEvent, render, screen } from "@testing-library/react";

import { ReasoningBlock } from "../components/ReasoningBlock";

describe("ReasoningBlock", () => {
  it("renders the reasoning text and toggles collapse", () => {
    render(<ReasoningBlock text="thinking hard" />);
    expect(screen.getByText("thinking hard")).toBeInTheDocument();
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-controls");
    expect(screen.getByRole("region", { name: "Reasoning details" })).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByText("thinking hard")).not.toBeInTheDocument();
  });

  it("renders nothing for empty text", () => {
    const { container } = render(<ReasoningBlock text="" />);
    expect(container.firstChild).toBeNull();
  });
});
