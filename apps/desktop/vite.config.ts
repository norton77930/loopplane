import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const webSrc = fileURLToPath(new URL("../web/src", import.meta.url));
const coworkPresentationEntry = fileURLToPath(
  new URL("../../packages/cowork-presentation/src/index.ts", import.meta.url),
);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@web": webSrc,
      "@loopplane/cowork-presentation": coworkPresentationEntry,
    },
  },
  test: {
    globals: true,
    environmentMatchGlobs: [["**/*.test.tsx", "jsdom"]],
    setupFiles: ["./src/test-setup.ts"],
  },
});
