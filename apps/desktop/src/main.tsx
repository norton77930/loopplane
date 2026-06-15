import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { type DesktopBridge, SidecarTransport } from "./sidecar";

const bridge = (window as unknown as { api?: DesktopBridge }).api;
const root = document.getElementById("root");
if (root && bridge) {
  createRoot(root).render(
    <StrictMode>
      <App transport={new SidecarTransport(bridge)} />
    </StrictMode>,
  );
}
