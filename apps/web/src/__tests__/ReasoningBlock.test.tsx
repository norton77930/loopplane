import { fireEvent, render, screen } from "@testing-library/react";

import { ReasoningBlock } from "../components/ReasoningBlock";

describe("ReasoningBlock", () => {
  it("renders the reasoning text and toggles collapse", () => {
    render(<ReasoningBlock text="thinking hard" />);
    expect(screen.getByText("thinking hard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("thinking hard")).not.toBeInTheDocument();
  });

  it("renders nothing for empty text", () => {
    const { container } = render(<ReasoningBlock text="" />);
    expect(container.firstChild).toBeNull();
  });
});
