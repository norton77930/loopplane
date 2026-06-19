import { fireEvent, render, screen } from "@testing-library/react";

import { ErrorBanner } from "../components/ErrorBanner";

describe("ErrorBanner", () => {
  it("shows a Retry button that fires the handler", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders the alert without a Retry when no handler is given", () => {
    render(<ErrorBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Retry")).not.toBeInTheDocument();
  });
});
