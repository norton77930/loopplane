declare const process: { env: { npm_package_json?: string } };

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const webRoot = process.env.npm_package_json
  ? process.env.npm_package_json.replace(/[\\/]package\.json$/, "")
  : ".";

export default defineConfig({
  root: webRoot,
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) return "vendor";
        },
      },
    },
  },
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