import { defineConfig } from "vitest/config";

/**
 * Shared-package Vitest config (T008).
 * Avoids @vitejs/plugin-react so the accepted package.json graph stays unchanged.
 */
export default defineConfig({
  test: {
    globals: true,
    passWithNoTests: true,
    environmentMatchGlobs: [["**/*.test.tsx", "jsdom"]],
    setupFiles: ["./src/test-setup.ts"],
  },
});
