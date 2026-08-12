import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createTransportFromWindow } from "./sidecar";

const root = document.getElementById("root");
const transport = createTransportFromWindow();
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App
        transport={transport}
        initialPhase={transport ? "ready" : "unavailable"}
      />
    </StrictMode>,
  );
}
