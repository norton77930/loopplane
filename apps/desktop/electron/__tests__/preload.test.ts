/**
 * Preload facade inventory (078 T037 / T029).
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const preloadPath = fileURLToPath(new URL("../preload.ts", import.meta.url));
const globalDts = fileURLToPath(
  new URL("../../src/global.d.ts", import.meta.url),
);

describe("preload session/project/workspace surface", () => {
  it("exposes frozen domain methods without raw channels or path APIs", () => {
    const src = readFileSync(preloadPath, "utf8");
    expect(src).toContain('exposeInMainWorld("loopplaneDesktop"');
    expect(src).toContain("Object.freeze");

    for (const name of [
      "list",
      "history",
      "rename",
      "setStarred",
      "delete",
      "fork",
      "createInteractive",
      "resumeInteractive",
      "releaseInteractive",
    ]) {
      expect(src).toContain(name);
    }
    expect(src).toContain("projects");
    expect(src).toContain("assignSession");
    expect(src).toContain("workspaces");
    expect(src).toContain("chooseAndBind");
    expect(src).toContain("chooseAndRelink");
    expect(src).toContain("revalidate");
    expect(src).toContain("permissionMode");

    expect(src).not.toContain("sidecar:send");
    expect(src).not.toContain("sidecar:line");
    expect(src).not.toMatch(/exposeInMainWorld\(\s*["']api["']/);
    expect(src).not.toContain("showOpenDialog");
    expect(src).not.toContain("fs.");
    expect(src).not.toContain("mutation_id");
    expect(src).not.toContain("jsonrpc");
    expect(src).toContain("payloadSubscriptionId !== subscriptionId");
    expect(src).not.toContain("_subscriptionId");
  });

  it("types sessions projects and workspaces on the global facade", () => {
    const dts = readFileSync(globalDts, "utf8");
    expect(dts).toContain("sessions");
    expect(dts).toContain("setStarred");
    expect(dts).toContain("projects");
    expect(dts).toContain("workspaces");
    expect(dts).toContain("chooseAndBind");
    expect(dts).toContain("chooseAndRelink");
  });

  it("keeps backup/restore native paths behind operation-specific typed methods", () => {
    const src = readFileSync(preloadPath, "utf8");
    const dts = readFileSync(globalDts, "utf8");

    for (const surface of [src, dts]) {
      expect(surface).toContain("backup");
      expect(surface).toContain("describe");
      expect(surface).toContain("chooseAndCreate");
      expect(surface).toContain("chooseAndValidateRestore");
      expect(surface).toContain("commitRestore");
      expect(surface).toContain("cancelRestore");
      expect(surface).not.toContain("destinationPath");
      expect(surface).not.toContain("sourcePath");
    }
    expect(src).not.toContain("showSaveDialog");
    expect(src).not.toContain("showOpenDialog");
  });
});
