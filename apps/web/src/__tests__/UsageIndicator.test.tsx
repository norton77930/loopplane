import { render, screen } from "@testing-library/react";

import { UsageIndicator } from "../components/UsageIndicator";
import { ZERO_USAGE } from "../state/chat";

describe("UsageIndicator", () => {
  it("shows the last turn and the session input/output totals", () => {
    render(
      <UsageIndicator
        usage={{
          last: { input_tokens: 10, output_tokens: 5, cached_tokens: 0, reasoning_tokens: 0 },
          total: { input_tokens: 10, output_tokens: 5, cached_tokens: 0, reasoning_tokens: 0 },
        }}
      />,
    );
    const usage = screen.getByTestId("usage");
    expect(usage).toHaveTextContent("10 in");
    expect(usage).toHaveTextContent("5 out");
  });

  it("shows cached and reasoning sub-counts only when non-zero", () => {
    render(
      <UsageIndicator
        usage={{ total: { input_tokens: 10, output_tokens: 5, cached_tokens: 3, reasoning_tokens: 2 } }}
      />,
    );
    const usage = screen.getByTestId("usage");
    expect(usage).toHaveTextContent("cached");
    expect(usage).toHaveTextContent("reasoning");
  });

  it("renders nothing when the session total is all-zero", () => {
    const { container } = render(<UsageIndicator usage={{ total: ZERO_USAGE }} />);
    expect(container.firstChild).toBeNull();
  });
});
