import { render, screen } from "@testing-library/react";

import { MenuIcon, PaperclipIcon, SendIcon } from "../components/icons/Icons";

describe("semantic icons", () => {
  it("stay decorative when their surrounding control provides the accessible name", () => {
    render(
      <>
        <MenuIcon data-testid="menu-icon" />
        <PaperclipIcon data-testid="paperclip-icon" />
        <SendIcon data-testid="send-icon" />
      </>,
    );

    for (const testId of ["menu-icon", "paperclip-icon", "send-icon"]) {
      const icon = screen.getByTestId(testId);
      expect(icon.tagName).toBe("svg");
      expect(icon).toHaveAttribute("aria-hidden", "true");
      expect(icon).toHaveAttribute("focusable", "false");
    }
  });
});
