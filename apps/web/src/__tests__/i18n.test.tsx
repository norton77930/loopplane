import { fireEvent, render, screen } from "@testing-library/react";

import { I18nProvider, t, useTranslation } from "../i18n/i18n";

describe("i18n", () => {
  beforeEach(() => localStorage.clear());

  it("looks up the active locale and never returns a blank", () => {
    expect(t("composer.send", "en")).toBe("Send");
    expect(t("composer.send", "zh-TW")).toBe("傳送");
    // a key absent from every map falls back to the key itself (never blank — FR-003)
    expect(t("totally.missing", "zh-TW")).toBe("totally.missing");
  });

  it("switches and persists the locale through the provider", () => {
    function Probe() {
      const { t, locale, setLocale } = useTranslation();
      return (
        <div>
          <span data-testid="label">{t("header.inspect")}</span>
          <span data-testid="locale">{locale}</span>
          <button type="button" onClick={() => setLocale("zh-TW")}>
            switch
          </button>
        </div>
      );
    }

    const view = render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("label").textContent).toBe("Inspect");
    fireEvent.click(screen.getByText("switch"));
    expect(screen.getByTestId("label").textContent).toBe("檢視");
    expect(localStorage.getItem("loopplane-locale")).toBe("zh-TW");

    view.unmount();
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("zh-TW"); // restored from storage
  });

  it("synchronizes the document language with the selected locale", () => {
    function Probe() {
      const { setLocale } = useTranslation();
      return (
        <button type="button" onClick={() => setLocale("zh-TW")}>switch language</button>
      );
    }

    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(document.documentElement.lang).toBe("en");

    fireEvent.click(screen.getByRole("button", { name: "switch language" }));
    expect(document.documentElement.lang).toBe("zh-TW");
  });
});
