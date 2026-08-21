/**
 * Delivery-reviewed package, sidecar freeze, and external-smoke contracts (078 T082).
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const desktopPackagePath = fileURLToPath(
  new URL("../../package.json", import.meta.url),
);
const rootLockPath = fileURLToPath(
  new URL("../../../../package-lock.json", import.meta.url),
);
const desktopLockPath = fileURLToPath(
  new URL("../../package-lock.json", import.meta.url),
);
const webLockPath = fileURLToPath(
  new URL("../../../web/package-lock.json", import.meta.url),
);

function readOptional(relativeUrl: string): string {
  const path = fileURLToPath(new URL(relativeUrl, import.meta.url));
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

function expectForbiddenTokenBoundary(source: string): void {
  expect(source).toContain("LOOPPLANE_STAGE_B_GITHUB_TOKEN");
  expect(source).toContain("GH_TOKEN");
  expect(source).toContain("GITHUB_TOKEN");
  expect(source).toContain("credential_environment_forbidden");
}

describe("accepted Desktop package metadata", () => {
  it("keeps the final-Stage-B entrypoints and sole wrapper routes unchanged", () => {
    const manifest = JSON.parse(readFileSync(desktopPackagePath, "utf8")) as {
      main: string;
      files: string[];
      scripts: Record<string, string>;
    };

    expect(manifest.main).toBe("dist-electron/main.js");
    expect(manifest.files).toEqual([
      "dist",
      "dist-electron",
      "electron-builder.yml",
      "package.json",
    ]);
    expect(manifest.scripts.package).toContain(
      "scripts/build-desktop-package.ps1",
    );
    expect(manifest.scripts["build:sidecar"]).toContain(
      "scripts/build-desktop-sidecar.ps1",
    );
    expect(manifest.scripts.build).toContain("tsconfig.main.json");
    expect(manifest.scripts.build).toContain("tsconfig.preload.json");
    expect(existsSync(rootLockPath)).toBe(true);
    expect(existsSync(desktopLockPath)).toBe(false);
    expect(existsSync(webLockPath)).toBe(false);
  });

  it("declares deterministic renderer, main, and preload emitted outputs", () => {
    const mainConfig = readOptional("../../tsconfig.main.json");
    const preloadConfig = readOptional("../../tsconfig.preload.json");
    const viteConfig = readOptional("../../vite.config.ts");

    expect(mainConfig).toContain("electron/main.ts");
    expect(mainConfig).toContain("dist-electron");
    expect(preloadConfig).toContain("electron/preload.ts");
    expect(preloadConfig).toContain("dist-electron");
    expect(viteConfig).toContain('base: "./"');
    expect(viteConfig).toContain("build:");
    expect(viteConfig).toContain('outDir: "dist"');
  });

  it("aligns electron-builder with emitted assets and the frozen sidecar", () => {
    const builder = readOptional("../../electron-builder.yml");
    const main = readOptional("../main.ts");

    expect(builder).toContain("dist/**/*");
    expect(builder).toContain("dist-electron/**/*");
    expect(builder).toContain("from: sidecar/dist");
    expect(builder).toContain("to: sidecar");
    expect(builder).toContain('- "**/*"');
    expect(main).toContain('app.isPackaged');
    expect(main).toContain('join(app.getAppPath(), "dist", "index.html")');
    expect(main).toContain('new URL("../dist/index.html"');
    expect(main).toContain('new URL("./preload.cjs"');
  });
});

describe("descriptor-only build wrappers", () => {
  it("makes the package wrapper the sole complete artifact route", () => {
    const wrapper = readOptional(
      "../../../../scripts/build-desktop-package.ps1",
    );

    expect(wrapper).toContain("DescriptorPath");
    expectForbiddenTokenBoundary(wrapper);
    expect(wrapper).toContain("AssertMaterializedInputs");
    expect(wrapper).toContain("npm ci");
    expect(wrapper).toContain("build-desktop-sidecar.ps1");
    expect(wrapper).toContain("electron-builder");
    expect(wrapper).not.toContain("loopplane-sidecar.spec");
    expect(wrapper).not.toMatch(/(^|\r?\n)\s*(?:&\s*)?pyinstaller(?:\.exe)?\b/i);
  });

  it("freezes only from descriptor-reviewed Python and source snapshots", () => {
    const wrapper = readOptional(
      "../../../../scripts/build-desktop-sidecar.ps1",
    );
    const spec = readOptional("../../sidecar/loopplane-sidecar.spec");
    const entrypoint = readOptional("../../sidecar/__main__.py");

    expect(wrapper).toContain("DescriptorPath");
    expectForbiddenTokenBoundary(wrapper);
    expect(wrapper).toContain("AssertMaterializedInputs");
    expect(wrapper).toContain("pyinstallerLockPath");
    expect(wrapper).toContain("runtimeRequirementsPath");
    expect(wrapper).toContain("pythonProjectRoot");
    expect(wrapper).toContain("reviewedSourceRoot");
    expect(wrapper).toContain("--extra anthropic");
    expect(wrapper).toContain("--extra gemini");
    expect(wrapper).toContain("--extra mcp");
    expect(wrapper).toContain("--extra net");
    expect(wrapper).toContain("--extra oauth");
    expect(wrapper).toContain("--extra openai");
    expect(wrapper).toContain("Scripts/pyinstaller.exe");
    expect(wrapper).toContain("loopplane-sidecar.spec");
    expect(wrapper).toContain("$bundleRoot = Join-Path $outputRoot 'loopplane-sidecar'");
    expect(wrapper).toContain("output_root = $bundleRoot");
    expect(wrapper).not.toMatch(/(^|\r?\n)\s*(?:&\s*)?pyinstaller(?:\.exe)?\b/i);
    expect(spec).toContain("SPECPATH");
    expect(spec).toContain('build_root / "src"');
    expect(spec).toContain('entrypoint = sidecar_root / "__main__.py"');
    expect(spec).toContain('collect_submodules("loopplane.adapters")');
    expect(spec).not.toContain('collect_submodules("loopplane")');
    expect(spec).toContain("exclude_binaries=True");
    expect(spec).toContain("COLLECT(");
    expect(spec).not.toContain('Analysis(\n    ["bridge.py"]');
    expect(entrypoint).toContain("from bridge import main");
  });
});

describe("Windows delivery workflow", () => {
  it("verifies immutable review authority before the token-free package route", () => {
    const workflow = readOptional("../../../../.github/workflows/desktop.yml");
    const verifierIndex = workflow.lastIndexOf("verify-desktop-stage-b.ps1");
    const packageIndex = workflow.lastIndexOf("build-desktop-package.ps1");
    const mappedTokenIndex = workflow.indexOf(
      "LOOPPLANE_STAGE_B_GITHUB_TOKEN: ${{ github.token }}",
    );

    expect(workflow).toContain("pull_request_review:");
    expect(workflow).toContain("types: [submitted]");
    expect(workflow).toContain("windows-latest");
    expect(workflow).toContain("contents: read");
    expect(workflow).toContain("pull-requests: read");
    expect(workflow).toContain("persist-credentials: false");
    expect(workflow).toContain("LOOPPLANE_DESKTOP_BOOTSTRAP_REVIEW_ID");
    expect(workflow).toContain("LOOPPLANE_DESKTOP_BOOTSTRAP_COMMIT_SHA");
    expect(workflow).toContain("LOOPPLANE_DESKTOP_FINAL_REVIEW_ID");
    expect(workflow).toContain("LOOPPLANE_DESKTOP_FINAL_COMMIT_SHA");
    expect(workflow).toContain("LOOPPLANE_DESKTOP_EXPECTED_APPROVER");
    expect(workflow).toContain("github.event.review.id");
    expect(workflow).toContain("github.event.review.commit_id");
    expect(workflow).toContain("-MaterializeAcceptedInputs");
    expect(workflow).toContain("-DescriptorPath");
    expect(verifierIndex).toBeGreaterThan(-1);
    expect(packageIndex).toBeGreaterThan(verifierIndex);
    expect(mappedTokenIndex).toBeGreaterThan(-1);
    expect(mappedTokenIndex).toBeLessThan(packageIndex);
    expect(workflow.slice(packageIndex)).not.toContain("${{ github.token }}");
    expect(workflow).not.toContain("pull_request_target");
  });

  it("covers every artifact determinant and invokes smoke from an external CWD", () => {
    const workflow = readOptional("../../../../.github/workflows/desktop.yml");

    for (const determinant of [
      "package.json",
      "package-lock.json",
      "pyproject.toml",
      "uv.lock",
      "apps/desktop/**",
      "apps/web/**",
      "packages/cowork-presentation/**",
      "src/**",
      "tests/**",
      "scripts/verify-desktop-stage-b.ps1",
      "scripts/build-desktop-sidecar.ps1",
      "scripts/build-desktop-package.ps1",
      "scripts/smoke-desktop-artifact.ps1",
      "docs/adr/0015-desktop-cowork-boundary.md",
      "specs/078-desktop-cowork-parity/**",
    ]) {
      expect(workflow).toContain(determinant);
    }
    // Push-Location only moves the PowerShell provider location, so it cannot
    // establish the external working directory the smoke asserts on: the run
    // stays in the checkout and fails closed before any UI Automation.
    expect(workflow).not.toMatch(/^\s*Push-Location\b/m);
    expect(workflow).toContain("-WorkingDirectory $runRoot");
    expect(workflow).toContain(
      "'-File', \"$env:GITHUB_WORKSPACE/scripts/smoke-desktop-artifact.ps1\"",
    );
    expect(workflow.indexOf("-WorkingDirectory $runRoot")).toBeLessThan(
      workflow.lastIndexOf("smoke-desktop-artifact.ps1"),
    );
    expect(workflow).toContain("'-Scenario', 'all'");
  });
});

describe("external packaged-artifact smoke boundary", () => {
  it("accepts only external application, state, evidence, profile, and CWD paths", () => {
    const smoke = readOptional(
      "../../../../scripts/smoke-desktop-artifact.ps1",
    );

    expect(smoke).toContain("AppExecutable");
    expect(smoke).toContain("ScratchRoot");
    expect(smoke).toContain("EvidencePath");
    expect(smoke).toContain("Scenario");
    expect(smoke).toContain("GeneratedProfile");
    expect(smoke).toContain("checkout_path_forbidden");
    expect(smoke).toContain("checkout_cwd_forbidden");
    expect(smoke).toContain("GetCurrentDirectory");
    expect(smoke).toContain("PYTHONPATH");
    expect(smoke).toContain("NODE_PATH");
  });

  it("uses fresh profiles and restores only copied sidecar failure variants", () => {
    const smoke = readOptional(
      "../../../../scripts/smoke-desktop-artifact.ps1",
    );

    for (const scenario of [
      "happy",
      "missing-sidecar",
      "corrupt-sidecar",
      "incompatible-sidecar",
      "all",
    ]) {
      expect(smoke).toContain(scenario);
    }
    expect(smoke).toContain("Invoke-SmokeScenario");
    expect(smoke).toContain("Restore-CopiedSidecar");
    expect(smoke).toContain("profile-");
    expect(smoke).toContain("LoopPlane smoke runtime diagnostic");
    expect(smoke).toContain("Wait-RuntimeUsable");
    expect(smoke).toContain("AddSeconds(10)");
    expect(smoke).toContain("FileMode]::CreateNew");
    // Pin the property — the driver records a SHA-256 digest for the artifact and
    // for every profile entry — not the cmdlet that computes it. Get-FileHash has
    // to be resolved from a module at call time and a hosted runner reported it as
    // not recognized, so the digests are computed with .NET instead.
    expect(smoke).not.toContain("Get-FileHash -LiteralPath");
    expect(smoke).toContain("artifact_sha256 = Get-Sha256File");
    expect(smoke).toContain("[System.Security.Cryptography.SHA256]::Create()");
  });
});
