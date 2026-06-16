import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { frozenSidecarName, resolveSidecar } from "../../electron/sidecar-spawn";

describe("resolveSidecar", () => {
  it("targets the bundled frozen sidecar in a packaged app", () => {
    const result = resolveSidecar({
      packaged: true,
      platform: "linux",
      resourcesPath: "/app/resources",
      devDir: "/dev/sidecar",
      exists: () => true,
    });

    expect(result.command).toBe("/app/resources/sidecar/loopplane-sidecar");
    expect(result.args).toEqual([]);
  });

  it("uses a per-platform name (.exe on Windows)", () => {
    expect(frozenSidecarName("linux")).toBe("loopplane-sidecar");
    expect(frozenSidecarName("win32")).toBe("loopplane-sidecar.exe");

    const result = resolveSidecar({
      packaged: true,
      platform: "win32",
      resourcesPath: "C:\\app\\resources",
      devDir: "C:\\dev\\sidecar",
      exists: () => true,
    });

    expect(result.command).toBe("C:\\app\\resources\\sidecar\\loopplane-sidecar.exe");
  });

  it("throws clearly when the bundled frozen sidecar is missing", () => {
    expect(() =>
      resolveSidecar({
        packaged: true,
        platform: "linux",
        resourcesPath: "/app/resources",
        devDir: "/dev/sidecar",
        exists: () => false,
      }),
    ).toThrow(/sidecar/i);
  });

  it("falls back to system python + the bridge in development", () => {
    const result = resolveSidecar({
      packaged: false,
      platform: "linux",
      resourcesPath: "/unused",
      devDir: "/dev/sidecar",
      exists: () => true,
    });

    expect(result.command).toBe("python");
    expect(result.args).toEqual(["/dev/sidecar/bridge.py"]);
  });
});

describe("freeze <-> package consistency", () => {
  it("the PyInstaller spec and the electron-builder config name the same frozen sidecar", () => {
    const spec = readFileSync(
      fileURLToPath(new URL("../../sidecar/loopplane-sidecar.spec", import.meta.url)),
      "utf8",
    );
    const config = readFileSync(
      fileURLToPath(new URL("../../electron-builder.yml", import.meta.url)),
      "utf8",
    );

    expect(spec).toContain("loopplane-sidecar");
    expect(config).toContain("loopplane-sidecar");
  });
});
