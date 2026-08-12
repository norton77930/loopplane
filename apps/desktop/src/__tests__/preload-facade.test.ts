/**
 * T029: preload exposes frozen typed facade, not raw IPC tunnel.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const preloadPath = fileURLToPath(
  new URL("../../electron/preload.ts", import.meta.url),
);
const globalDts = fileURLToPath(new URL("../global.d.ts", import.meta.url));

describe("preload facade", () => {
  it("exposes loopplaneDesktop and does not expose raw send/onLine tunnel", () => {
    const src = readFileSync(preloadPath, "utf8");
    expect(src).toContain('exposeInMainWorld("loopplaneDesktop"');
    expect(src).toContain("Object.freeze");
    expect(src).toContain("createInteractive");
    expect(src).toContain("resumeInteractive");
    expect(src).toContain("releaseInteractive");
    expect(src).toContain("answerApproval");
    expect(src).toContain("subscribeStatus");
    expect(src).toContain("interaction");
    expect(src).toContain("projects");
    expect(src).toContain("workspaces");
    expect(src).toContain("chooseAndBind");
    expect(src).toContain("setStarred");
    // No raw tunnel re-export
    expect(src).not.toMatch(/exposeInMainWorld\(\s*["']api["']/);
    expect(src).not.toContain("sidecar:send");
    expect(src).not.toContain("sidecar:line");
    // Subscribe must not invoke RPC
    expect(src).toMatch(/subscribeStatus[\s\S]*wrapSubscribe/);
    expect(src).toMatch(/subscribe:[\s\S]*wrapSubscribe/);
  });

  it("global.d.ts types the frozen facade", () => {
    const dts = readFileSync(globalDts, "utf8");
    expect(dts).toContain("loopplaneDesktop");
    expect(dts).toContain("LoopPlaneDesktopApi");
    expect(dts).toContain("createInteractive");
    expect(dts).toContain("answerApproval");
  });
});
