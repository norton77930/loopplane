import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppRoot } from "./AppRoot";
import { I18nProvider } from "./i18n/i18n";
import { initTheme } from "./theme/theme";
import "./styles.css";

// Apply the resolved theme (stored choice or OS preference) before first paint (FR-013).
initTheme();

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <I18nProvider>
        <AppRoot />
      </I18nProvider>
    </StrictMode>,
  );
}
