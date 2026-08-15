/**
 * One vocabulary for the states a person has to act on.
 *
 * The runtime's own names for these — `acceptEdits`, `read_only`, "not owner" —
 * are precise and say nothing about consequence. A control surface that prints
 * them is asking the reader to already know the implementation. These map each
 * state to what it means for the next thing the agent does, without softening
 * it: someone deciding whether to approve a tool call needs the consequence, not
 * reassurance.
 */

import type { PresentationAgentControls } from "./models";

const PERMISSION_POSTURE: Record<string, string> = {
  plan: "Planning only — no changes",
  acceptEdits: "Edits files without asking",
  dontAsk: "Runs allowed tools without asking",
  bypassPermissions: "Approvals bypassed",
};

/** The default when no mode is selected: every tool call is offered for review. */
export const ASKS_FIRST_POSTURE = "Asks before acting";

/**
 * How much the agent may do without asking, for the run that is happening or
 * the one that would happen next. Returns null when the host cannot say, so a
 * caller shows nothing rather than guessing a posture.
 */
export function permissionPostureLabel(
  controls: PresentationAgentControls | null | undefined,
): string | null {
  if (!controls || controls.unavailable) return null;
  const run = controls.activeRun ?? controls.lastAcceptedRun ?? null;
  if (run?.planActive) return PERMISSION_POSTURE.plan!;
  const mode = run?.mode ?? controls.defaultMode;
  if (!mode) return ASKS_FIRST_POSTURE;
  return PERMISSION_POSTURE[mode] ?? ASKS_FIRST_POSTURE;
}
