import { fireEvent, render, screen } from "@testing-library/react";

import { FollowUpSuggestions } from "../components/FollowUpSuggestions";

describe("FollowUpSuggestions", () => {
  const suggestions = [
    {
      id: "continue",
      reason: "settled" as const,
      text: "Summarize the result and propose next steps.",
    },
  ];

  it("exposes optional proposals as an accessible keyboard-reachable group", () => {
    const onSelect = vi.fn();
    render(
      <FollowUpSuggestions
        suggestions={suggestions}
        onSelect={onSelect}
        onDismiss={() => undefined}
      />,
    );

    const group = screen.getByRole("region", { name: "Optional follow-up suggestions" });
    expect(group).toHaveTextContent("Optional user input");
    const button = screen.getByRole("button", {
      name: "Summarize the result and propose next steps.",
    });
    fireEvent.click(button);
    expect(onSelect).toHaveBeenCalledWith(suggestions[0]);
  });

  it("dismisses a proposal without selecting it", () => {
    const onSelect = vi.fn();
    const onDismiss = vi.fn();
    render(
      <FollowUpSuggestions
        suggestions={suggestions}
        onSelect={onSelect}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Dismiss suggestion" }));
    expect(onDismiss).toHaveBeenCalledWith("continue");
    expect(onSelect).not.toHaveBeenCalled();
  });
});
