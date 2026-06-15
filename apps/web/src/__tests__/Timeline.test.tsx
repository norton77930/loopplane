import { render, screen } from "@testing-library/react";

import { Timeline } from "../components/Timeline";

describe("Timeline", () => {
  it("renders tool activity and termination (metadata only)", () => {
    render(
      <Timeline
        entries={[
          { kind: "tool", callId: "c1", name: "echo", outcome: "success" },
          { kind: "terminated", reason: "natural-completion", turns: 1 },
        ]}
      />,
    );
    expect(screen.getByText(/tool echo/)).toBeInTheDocument();
    expect(screen.getByText(/success/)).toBeInTheDocument();
    expect(screen.getByText(/natural-completion/)).toBeInTheDocument();
  });
});
