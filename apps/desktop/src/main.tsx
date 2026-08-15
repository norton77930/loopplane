import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { DesktopI18nProvider } from "./i18n";
import { createTransportFromWindow } from "./sidecar";
import "./styles.css";

const root = document.getElementById("root");
const transport = createTransportFromWindow();
if (root) {
  createRoot(root).render(
    <StrictMode>
      <DesktopI18nProvider>
        <App
          transport={transport}
          initialPhase={transport ? "starting" : "unavailable"}
        />
      </DesktopI18nProvider>
    </StrictMode>,
  );
}
