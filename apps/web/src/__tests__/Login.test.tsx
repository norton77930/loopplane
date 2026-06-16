import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Login } from "../components/Login";

describe("Login", () => {
  it("submits a non-empty token", () => {
    const onSubmit = vi.fn();
    render(<Login onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("access token"), {
      target: { value: "tok-alice" },
    });
    fireEvent.click(screen.getByText("Log in"));

    expect(onSubmit).toHaveBeenCalledWith("tok-alice");
  });

  it("does not submit an empty token", () => {
    const onSubmit = vi.fn();
    render(<Login onSubmit={onSubmit} />);

    fireEvent.click(screen.getByText("Log in"));

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
