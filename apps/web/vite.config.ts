import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy the API to a running unit-011 web/API host during development.
    proxy: { "/v1": "http://localhost:8000" },
  },
  test: {
    globals: true,
    // The pure core runs in node; component tests (*.test.tsx) use jsdom.
    environmentMatchGlobs: [["**/*.test.tsx", "jsdom"]],
    setupFiles: ["./src/test-setup.ts"],
  },
});
