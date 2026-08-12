import { builtinModules } from "node:module";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { build as viteBuild, type Plugin } from "vite";
import { defineConfig } from "vitest/config";

const webSrc = fileURLToPath(new URL("../web/src", import.meta.url));
const coworkPresentationEntry = fileURLToPath(
  new URL("../../packages/cowork-presentation/src/index.ts", import.meta.url),
);
const electronExternal = [
  "electron",
  ...builtinModules,
  ...builtinModules.map((name) => `node:${name}`),
];

function emitElectronBundles(): Plugin {
  return {
    name: "loopplane-electron-bundles",
    apply: "build",
    async closeBundle() {
      await viteBuild({
        configFile: false,
        build: {
          emptyOutDir: true,
          lib: {
            entry: fileURLToPath(new URL("./electron/main.ts", import.meta.url)),
            formats: ["es"],
            fileName: () => "main.js",
          },
          minify: false,
          outDir: "dist-electron",
          rollupOptions: { external: electronExternal },
          target: "es2022",
        },
      });
      await viteBuild({
        configFile: false,
        build: {
          emptyOutDir: false,
          lib: {
            entry: fileURLToPath(
              new URL("./electron/preload.ts", import.meta.url),
            ),
            formats: ["cjs"],
            fileName: () => "preload.cjs",
          },
          minify: false,
          outDir: "dist-electron",
          rollupOptions: { external: electronExternal },
          target: "es2022",
        },
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), emitElectronBundles()],
  build: {
    outDir: "dist",
  },
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
