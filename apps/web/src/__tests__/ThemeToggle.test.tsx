import { fireEvent, render, screen } from "@testing-library/react";

import { ThemeToggle } from "../components/ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("toggles the theme and persists the choice", () => {
    render(<ThemeToggle />);
    const button = screen.getByLabelText("toggle theme");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    fireEvent.click(button);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("loopplane-theme")).toBe("dark");
  });
});
