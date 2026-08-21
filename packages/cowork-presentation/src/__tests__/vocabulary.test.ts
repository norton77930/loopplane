import { describe, expect, it } from "vitest";

import type { PresentationAgentControls } from "../models";
import {
  ASKS_FIRST_POSTURE,
  VOCABULARY_EN,
  paneReadOnlyReason,
  paneStateLabel,
  permissionPostureLabel,
  toolConsequence,
} from "../vocabulary";

function controls(
  overrides: Partial<PresentationAgentControls> = {},
): PresentationAgentControls {
  return {
    sessionId: "s1",
    defaultMode: null,
    selectableModes: [],
    activeRun: null,
    lastAcceptedRun: null,
    budget: {
      tracking: "unknown",
      pricing: "unpriced",
      sessionGuard: "unknown",
      monthlyGuard: "unknown",
    },
    actions: [],
    unavailable: false,
    ...overrides,
  };
}

describe("permissionPostureLabel", () => {
  it("says nothing when the host cannot say", () => {
    expect(permissionPostureLabel(null)).toBeNull();
    expect(permissionPostureLabel(controls({ unavailable: true }))).toBeNull();
  });

  it("defaults to asking first when no mode is chosen", () => {
    expect(permissionPostureLabel(controls())).toBe(ASKS_FIRST_POSTURE);
  });

  it("describes the consequence, not the mode id", () => {
    expect(
      permissionPostureLabel(controls({ defaultMode: "acceptEdits" })),
    ).toBe("posture.acceptEdits");
    expect(
      permissionPostureLabel(controls({ defaultMode: "bypassPermissions" })),
    ).toBe("posture.bypassPermissions");
  });

  it("prefers the active run over the default", () => {
    expect(
      permissionPostureLabel(
        controls({
          defaultMode: "acceptEdits",
          activeRun: { mode: "dontAsk", state: "running", planActive: false },
        }),
      ),
    ).toBe("posture.dontAsk");
  });

  it("reports plan mode whenever a plan is active", () => {
    expect(
      permissionPostureLabel(
        controls({
          activeRun: { mode: "acceptEdits", state: "running", planActive: true },
        }),
      ),
    ).toBe("posture.plan");
  });

  it("shows an unrecognized mode rather than the reassuring default", () => {
    // A future mode more permissive than "asks first" must not be described as
    // asking first just because this table has not caught up.
    expect(permissionPostureLabel(controls({ defaultMode: "yolo" }))).toBe(
      "yolo",
    );
  });
});

describe("paneStateLabel", () => {
  it("names what the pane can do", () => {
    expect(paneStateLabel("interactive", true)).toBe("pane.driving");
    expect(paneStateLabel("read_only", false)).toBe("pane.readOnly");
    expect(paneStateLabel("interactive", false)).toBe("pane.interactive");
  });

  it("does not invent a state it was not given", () => {
    expect(paneStateLabel(null, null)).toBe("pane.unknown");
  });
});

describe("paneReadOnlyReason", () => {
  it("stays quiet for the pane that holds the lease", () => {
    expect(paneReadOnlyReason(true, true)).toBeNull();
  });

  it("distinguishes contended from idle", () => {
    expect(paneReadOnlyReason(false, true)).toBe("pane.otherRunning");
    expect(paneReadOnlyReason(false, false)).toBe("pane.noneRunning");
  });
});

describe("toolConsequence", () => {
  it.each([
    ["run_command", /runs a command on this computer/i],
    ["edit_file", /changes a file in your workspace/i],
    ["web_fetch", /downloads a page from the internet/i],
    ["spawn_subagent", /starts a second agent run/i],
  ])("states what allowing %s does", (tool, pattern) => {
    const key = toolConsequence(tool)!;
    expect(VOCABULARY_EN[key]).toMatch(pattern);
  });

  it("says nothing about a tool it does not know", () => {
    // A confident sentence about an unknown tool is worse than no sentence.
    expect(toolConsequence("some_plugin_tool")).toBeNull();
  });
});

describe("vocabulary coverage", () => {
  it("has English for every key the vocabulary can return", () => {
    // A key with no entry renders as the key itself, which is how a missing
    // translation shows up as `posture.plan` in the middle of a sentence.
    const returned = [
      ASKS_FIRST_POSTURE,
      paneStateLabel("read_only", false),
      paneStateLabel("interactive", true),
      paneStateLabel(null, true),
      paneReadOnlyReason(false, true)!,
      paneReadOnlyReason(false, false)!,
      permissionPostureLabel(controls({ defaultMode: "acceptEdits" }))!,
      permissionPostureLabel(controls({ defaultMode: "bypassPermissions" }))!,
      permissionPostureLabel(
        controls({ activeRun: { mode: "x", state: "s", planActive: true } }),
      )!,
      "pane.takeOver",
      "pane.thisPane",
      "approval.question",
      ...[
        "run_command", "edit_file", "write_file", "notebook_edit", "undo_file",
        "web_fetch", "web_search", "spawn_subagent", "memory_write",
        "message_send", "swarm_dispatch", "schedule_create", "schedule_cancel",
        "task_create", "task_stop", "read_file", "glob_files", "search_files",
        "grep",
      ].map((tool) => toolConsequence(tool)!),
    ];

    for (const key of returned) {
      expect(VOCABULARY_EN[key], `no English for ${key}`).toBeTruthy();
    }
  });
});
