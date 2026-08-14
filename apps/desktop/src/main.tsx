import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createTransportFromWindow } from "./sidecar";
import "./styles.css";

const root = document.getElementById("root");
const transport = createTransportFromWindow();
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App
        transport={transport}
        initialPhase={transport ? "starting" : "unavailable"}
      />
    </StrictMode>,
  );
}
