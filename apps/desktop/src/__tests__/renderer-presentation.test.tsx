/**
 * Renderer presentation contracts.
 *
 * Two properties that every other gate happened to miss. The packaged smoke
 * asserts an accessibility tree, Vitest asserts DOM roles, and the shared
 * accessibility CSS tests assert reflow at 320px — all of which an entirely
 * unstyled page satisfies. The desktop renderer shipped without loading any
 * stylesheet at all and stayed green everywhere.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen } from "@testing-library/react";

import { App } from "../App";
import type { SidecarTransport } from "../sidecar";

function source(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}

describe("renderer stylesheet delivery", () => {
  it("loads the shared design system from the renderer entry", () => {
    const entry = source("../main.tsx");
    const stylesheetImport = entry.match(/^import\s+"(\.[^"]*\.css)";$/m);
    expect(
      stylesheetImport,
      "main.tsx must import a stylesheet, or the renderer paints unstyled HTML",
    ).not.toBeNull();

    const stylesheet = source(`../${stylesheetImport![1].replace(/^\.\//, "")}`);
    expect(
      stylesheet,
      "the renderer stylesheet must pull in the shared design system rather " +
        "than restating it",
    ).toContain("@loopplane/cowork-presentation/styles.css");
  });

  it("resolves the shared stylesheet specifier ahead of the package entry", () => {
    // A string alias matches by prefix, so aliasing the bare package name
    // alone sends the `/styles.css` subpath into the index module's path and
    // the build fails to resolve it.
    const config = source("../../vite.config.ts");
    const stylesAlias = config.indexOf(
      '"@loopplane/cowork-presentation/styles.css"',
    );
    const entryAlias = config.indexOf('"@loopplane/cowork-presentation":');
    expect(stylesAlias, "the styles subpath needs its own alias").toBeGreaterThan(
      -1,
    );
    expect(
      stylesAlias,
      "the subpath alias must be declared before the package alias",
    ).toBeLessThan(entryAlias);
  });
});

/**
 * The fixed Name/ControlType pairs `scripts/smoke-desktop-artifact.ps1` drives
 * the packaged application through. `Find-UniqueElement` fails the smoke unless
 * each pair matches exactly one element, so this is the same cardinality check
 * one layer down: a rename or a duplicate is caught here in seconds instead of
 * in a packaged UI Automation run.
 */
const SMOKE_LOCATORS: ReadonlyArray<{ name: string; role: string }> = [
  { name: "LoopPlane smoke runtime status", role: "group" },
  { name: "LoopPlane smoke new session", role: "button" },
  { name: "LoopPlane smoke prompt", role: "textbox" },
  { name: "LoopPlane smoke submit", role: "button" },
  { name: "LoopPlane smoke latest outcome", role: "group" },
  { name: "LoopPlane smoke session list", role: "list" },
  { name: "LoopPlane smoke runtime diagnostic", role: "group" },
];

function stubTransport(): SidecarTransport {
  return {
    run: async function* () {
      // no events
    },
    answerApproval: () => undefined,
    answerQuestion: () => undefined,
    cancel: () => undefined,
    status: async () => ({ ready: true }),
    dispose: async () => undefined,
    listSessions: async () => [],
    listProjects: async () => [],
    listWorkspaces: async () => [],
    setDraft: () => undefined,
    clearDraft: () => undefined,
    activeSessionId: null,
    activeSubscriptionId: null,
  } as unknown as SidecarTransport;
}

describe("packaged smoke locators", () => {
  it("exposes every fixed locator exactly once", () => {
    render(<App transport={stubTransport()} />);

    for (const { name, role } of SMOKE_LOCATORS) {
      const matches = screen.queryAllByRole(role, { name });
      expect(
        matches.length,
        `${role} named "${name}" must appear exactly once for the packaged ` +
          `smoke to drive it; found ${matches.length}`,
      ).toBe(1);
    }
  });

  it("keeps the prompt programmatically settable after the multi-line change", () => {
    // The smoke fills the prompt through UI Automation's ValuePattern
    // (`$prompt.SetValue(...)`, scripts/smoke-desktop-artifact.ps1). jsdom cannot
    // exercise UIA, so this pins the properties that pattern rests on: a real
    // form control that reports a value and accepts one set from outside a user
    // gesture. Chromium exposes ValuePattern on `textarea` as it did on `input`,
    // but only a packaged smoke run proves that end to end.
    render(<App transport={stubTransport()} />);

    const prompt = screen.getByRole("textbox", { name: "LoopPlane smoke prompt" });

    expect(prompt.tagName).toBe("TEXTAREA");
    expect(prompt).not.toBeDisabled();
    fireEvent.change(prompt, { target: { value: "loopplane packaged smoke" } });
    expect((prompt as HTMLTextAreaElement).value).toBe("loopplane packaged smoke");
  });

  it("sends on Enter but not while an input method is composing", () => {
    // Enter accepts a candidate in Chinese, Japanese and Korean input; sending
    // there would fire off a half-finished word.
    render(<App transport={stubTransport()} />);
    const prompt = screen.getByRole("textbox", { name: "LoopPlane smoke prompt" });
    fireEvent.change(prompt, { target: { value: "你好" } });

    fireEvent.keyDown(prompt, { key: "Enter", isComposing: true });
    expect((prompt as HTMLTextAreaElement).value).toBe("你好");

    fireEvent.keyDown(prompt, { key: "Enter", shiftKey: true });
    expect((prompt as HTMLTextAreaElement).value).toBe("你好");

    fireEvent.keyDown(prompt, { key: "Enter" });
    expect((prompt as HTMLTextAreaElement).value).toBe("");
  });
});
