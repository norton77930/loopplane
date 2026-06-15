import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const webSrc = fileURLToPath(new URL("../web/src", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@web": webSrc } },
  test: {
    globals: true,
    environmentMatchGlobs: [["**/*.test.tsx", "jsdom"]],
    setupFiles: ["./src/test-setup.ts"],
  },
});
