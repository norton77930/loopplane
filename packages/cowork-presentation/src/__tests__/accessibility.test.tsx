/**
 * Focused a11y unit checks (078 T050 subset).
 *
 * Full six-viewport Chromium matrix is recorded as RED inventory in
 * implementation-evidence until T055 styling lands.
 */

// @ts-expect-error Vitest provides Node built-ins at runtime; the package tsconfig omits Node types.
import { readFileSync } from "node:fs";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalDialog } from "../components/ApprovalDialog";
import { CoworkShell } from "../components/CoworkShell";
import { InspectionSidebar } from "../components/InspectionSidebar";
import { QuestionDialog } from "../components/QuestionDialog";
import { RuntimeUnavailable } from "../components/RuntimeUnavailable";
import * as focus from "../focus";
import * as presentation from "../index";
import {
  focusElement,
  prefersReducedMotion,
  restoreFocus,
} from "../focus";
import { createEmptyWorkspace, openPane } from "../panes/state";

const sharedStyles = readFileSync("src/styles.css", "utf8");

describe("focus helpers (T050 unit subset)", () => {
  it("keeps the packaged-smoke diagnostic group in the accessibility tree when healthy", () => {
    render(<RuntimeUnavailable active={false}>No runtime diagnostic.</RuntimeUnavailable>);

    const diagnostic = screen.getByRole("group", {
      name: "LoopPlane smoke runtime diagnostic",
    });
    expect(diagnostic).not.toHaveAttribute("aria-hidden", "true");
    expect(diagnostic).toHaveAttribute("aria-live", "off");
  });

  it("exposes the shared accessibility surface from the package entrypoint", () => {
    expect(Reflect.get(presentation, "ApprovalDialog")).toBeTypeOf("function");
    expect(Reflect.get(presentation, "QuestionDialog")).toBeTypeOf("function");
    expect(Reflect.get(presentation, "dismissOnEscape")).toBeTypeOf("function");
  });

  it("declares high-zoom reflow, reduced-motion, and forced-color cues", () => {
    expect(sharedStyles).toContain("overflow-x: clip");
    expect(sharedStyles).toContain("max-width: min(100%, 42rem)");
    expect(sharedStyles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(sharedStyles).toContain("@media (forced-colors: active)");
    expect(sharedStyles).toContain("outline: 2px solid CanvasText");
  });

  it("retains the Web shell base alongside T055 pane and dialog additions", () => {
    for (const selector of [
      ".shell {",
      ".messages {",
      ".modal-backdrop {",
      ".capability-settings {",
      ".cowork-shell {",
    ]) {
      expect(sharedStyles).toContain(selector);
    }
  });

  it("focusElement is a no-op for null", () => {
    expect(() => focusElement(null)).not.toThrow();
  });

  it("restoreFocus prefers previous when still mounted", () => {
    const a = document.createElement("button");
    const b = document.createElement("button");
    document.body.append(a, b);
    a.focus();
    restoreFocus(a, b);
    expect(document.activeElement).toBe(a);
    a.remove();
    b.remove();
  });

  it("prefersReducedMotion reads matchMedia", () => {
    expect(
      prefersReducedMotion(() => ({ matches: true })),
    ).toBe(true);
    expect(
      prefersReducedMotion(() => ({ matches: false })),
    ).toBe(false);
  });

  it("moves pane focus deterministically with ArrowRight", () => {
    let workspace = createEmptyWorkspace();
    workspace = openPane(workspace, { paneId: "one", sessionId: "s1", title: "One" });
    workspace = openPane(workspace, { paneId: "two", sessionId: "s2", title: "Two" });
    const onFocusPane = vi.fn();

    render(
      <CoworkShell
        workspace={workspace}
        onFocusPane={onFocusPane}
        onClosePane={vi.fn()}
        onRequestInteractive={vi.fn()}
      >
        <main>Conversation</main>
      </CoworkShell>,
    );

    const first = screen.getByRole("tab", { name: "One (read-only)" });
    const second = screen.getByRole("tab", { name: "Two (read-only)" });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });

    expect(onFocusPane).toHaveBeenCalledWith("two");
    expect(document.activeElement).toBe(second);
  });

  it("closes the inspection sidebar on Escape and restores its opener", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    const onClose = vi.fn();

    render(
      <InspectionSidebar
        onClose={onClose}
        returnFocus={opener}
      />,
    );

    const sidebar = screen.getByRole("complementary", { name: "Inspection" });
    fireEvent.keyDown(sidebar, { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("exports an Escape dismissal helper that restores the dialog opener", () => {
    const dismissOnEscape = Reflect.get(focus, "dismissOnEscape");
    expect(dismissOnEscape).toBeTypeOf("function");

    const opener = document.createElement("button");
    const fallback = document.createElement("button");
    document.body.append(opener, fallback);
    const dismiss = vi.fn();
    const preventDefault = vi.fn();
    (dismissOnEscape as (event: { key: string; preventDefault(): void }, onDismiss: () => void, previous: HTMLElement, fallback: HTMLElement) => boolean)(
      { key: "Escape", preventDefault },
      dismiss,
      opener,
      fallback,
    );

    expect(preventDefault).toHaveBeenCalledOnce();
    expect(dismiss).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(opener);
    opener.remove();
    fallback.remove();
  });

  it("denies an approval dialog on Escape and returns focus", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    const onDecide = vi.fn();
    render(<ApprovalDialog toolName="shell" onDecide={onDecide} returnFocus={opener} />);

    const dialog = screen.getByRole("dialog", { name: "Approval request" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Allow" }));
    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(onDecide).toHaveBeenCalledWith({ allow: false });
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("closes a question dialog on Escape and returns focus", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    const onClose = vi.fn();
    render(
      <QuestionDialog
        prompt="Continue?"
        options={["Yes"]}
        onAnswer={vi.fn()}
        onClose={onClose}
        returnFocus={opener}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "Question" });
    expect(document.activeElement).toBe(screen.getByRole("checkbox", { name: "Yes" }));
    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});
