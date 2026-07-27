import { useState } from "react";

import { useTranslation } from "../i18n/i18n";
import { initTheme, toggleTheme, type Theme } from "../theme/theme";

// A light/dark toggle bound to the theme module (FR-013). Initializes from the resolved theme
// (stored choice, else system preference) and flips + persists on click.
export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(() => initTheme());
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={t("theme.toggle")}
      title={theme === "dark" ? t("theme.switchLight") : t("theme.switchDark")}
      onClick={() => setTheme((current) => toggleTheme(current))}
    >
      {theme === "dark" ? t("theme.light") : t("theme.dark")}
    </button>
  );
}
