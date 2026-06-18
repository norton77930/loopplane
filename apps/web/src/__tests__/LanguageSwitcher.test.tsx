import { fireEvent, render, screen } from "@testing-library/react";

import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { I18nProvider } from "../i18n/i18n";

describe("LanguageSwitcher", () => {
  beforeEach(() => localStorage.clear());

  it("lists English and Traditional Chinese and switches", () => {
    render(
      <I18nProvider>
        <LanguageSwitcher />
      </I18nProvider>,
    );
    expect(screen.getByRole("option", { name: "English" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "繁體中文" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("language"), { target: { value: "zh-TW" } });
    expect(localStorage.getItem("loopplane-locale")).toBe("zh-TW");
  });
});
