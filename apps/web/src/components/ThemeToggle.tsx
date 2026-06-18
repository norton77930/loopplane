import { useState } from "react";

import { initTheme, toggleTheme, type Theme } from "../theme/theme";

// A light/dark toggle bound to the theme module (FR-013). Initializes from the resolved theme
// (stored choice, else system preference) and flips + persists on click.
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => initTheme());
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label="toggle theme"
      title={theme === "dark" ? "Switch to light" : "Switch to dark"}
      onClick={() => setTheme((current) => toggleTheme(current))}
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
