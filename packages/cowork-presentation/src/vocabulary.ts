/**
 * One vocabulary for the states a person has to act on.
 *
 * The runtime's own names for these — `acceptEdits`, `read_only`, "not owner" —
 * are precise and say nothing about consequence. A control surface that prints
 * them is asking the reader to already know the implementation. These map each
 * state to what it means for the next thing the agent does, without softening
 * it: someone deciding whether to approve a tool call needs the consequence, not
 * reassurance.
 *
 * Each function returns a translation *key*, not a sentence, so the same
 * vocabulary reaches a reader in their own language. The English text lives in
 * the shared provider's fallback messages, so a host that supplies no messages
 * at all still gets readable English.
 */

import type { PresentationAgentControls } from "./models";

const PERMISSION_POSTURE: Record<string, string> = {
  plan: "posture.plan",
  acceptEdits: "posture.acceptEdits",
  dontAsk: "posture.dontAsk",
  bypassPermissions: "posture.bypassPermissions",
};

/** The default when no mode is selected: every tool call is offered for review. */
export const ASKS_FIRST_POSTURE = "posture.asksFirst";

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
  // An unrecognized mode returns its own id, not the cautious default. If a
  // future mode is more permissive than "asks first" and this table has not
  // caught up, showing the safe phrase would be a false reassurance in exactly
  // the place a reader is deciding how much to trust the agent. An unknown key
  // falls through the lookup unchanged, so the id is what appears.
  return PERMISSION_POSTURE[mode] ?? mode;
}

/**
 * What allowing a tool actually does, for the built-in tools.
 *
 * "Approve tool run_command?" is not a decidable question for someone who does
 * not already know what `run_command` is, and this is the one dialog where
 * getting the wording wrong has consequences. So: state the effect, do not
 * soften it, and return null for anything not listed rather than guessing —
 * a confident sentence about an unknown tool is worse than no sentence.
 */
const TOOL_CONSEQUENCE: Record<string, string> = {
  write_file: "tool.write_file",
  edit_file: "tool.edit_file",
  notebook_edit: "tool.notebook_edit",
  undo_file: "tool.undo_file",
  run_command: "tool.run_command",
  web_fetch: "tool.web_fetch",
  web_search: "tool.web_search",
  spawn_subagent: "tool.spawn_subagent",
  memory_write: "tool.memory_write",
  message_send: "tool.message_send",
  swarm_dispatch: "tool.swarm_dispatch",
  schedule_create: "tool.schedule_create",
  schedule_cancel: "tool.schedule_cancel",
  task_create: "tool.task_create",
  task_stop: "tool.task_stop",
  read_file: "tool.read_file",
  glob_files: "tool.glob_files",
  search_files: "tool.search_files",
  grep: "tool.grep",
};

export function toolConsequence(toolName: string): string | null {
  return TOOL_CONSEQUENCE[toolName] ?? null;
}

/**
 * What a pane can do right now.
 *
 * `mode` is `interactive` or `read_only` and `leaseOwner` says whether this pane
 * holds the single interactive lease. Printed raw — "Mode: read_only", "Lease:
 * not owner" — that is two rows of implementation naming a reader has to
 * assemble into one fact with no hint that it is recoverable.
 */
export function paneStateLabel(
  mode: string | null | undefined,
  leaseOwner: boolean | null | undefined,
): string {
  if (leaseOwner) return "pane.driving";
  if (mode === "read_only") return "pane.readOnly";
  if (mode === "interactive") return "pane.interactive";
  return mode || "pane.unknown";
}

/** Why a pane is read-only, when the host knows another pane is holding it. */
export function paneReadOnlyReason(
  leaseOwner: boolean | null | undefined,
  otherPaneHoldsLease: boolean | null | undefined,
): string | null {
  if (leaseOwner) return null;
  return otherPaneHoldsLease ? "pane.otherRunning" : "pane.noneRunning";
}

/** English for every key above; hosts merge their own locales over this. */
export const VOCABULARY_EN: Record<string, string> = {
  "posture.asksFirst": "Asks before acting",
  "posture.plan": "Planning only — no changes",
  "posture.acceptEdits": "Edits files without asking",
  "posture.dontAsk": "Runs allowed tools without asking",
  "posture.bypassPermissions": "Approvals bypassed",

  "pane.driving": "Driving this session",
  "pane.readOnly": "Read-only",
  "pane.interactive": "Interactive",
  "pane.unknown": "Unknown",
  "pane.otherRunning": "Another pane is running.",
  "pane.noneRunning": "No pane is running yet.",
  "pane.takeOver": "Take over",
  "pane.readOnlyBanner": "This pane is read-only.",
  "pane.thisPane": "This pane",

  "inspection.heading": "Inspection",
  "inspection.unavailable": "Inspection unavailable.",
  "inspection.session": "Session",
  "inspection.cost": "Cost",
  "inspection.context": "Context",
  "inspection.uploads": "Uploads",
  "inspection.artifacts": "Artifacts",
  "inspection.posture": "Control posture",
  "inspection.pricing": "Pricing",
  "inspection.capabilities": "Capabilities",
  "inspection.detail": "Detail",
  "value.unavailable": "Unavailable",
  "value.unknown": "Unknown",
  "value.unpriced": "Unpriced",

  "approval.question": "Let LoopPlane use",
  "approval.allow": "Allow",
  "approval.deny": "Deny",
  "approval.alwaysAllow": "Always allow this session",
  "tool.write_file": "This creates or overwrites a file in your workspace.",
  "tool.edit_file": "This changes a file in your workspace.",
  "tool.notebook_edit": "This changes a notebook in your workspace.",
  "tool.undo_file": "This restores a file to how it was before an earlier edit.",
  "tool.run_command": "This runs a command on this computer.",
  "tool.web_fetch": "This downloads a page from the internet.",
  "tool.web_search": "This sends your query to a search provider on the internet.",
  "tool.spawn_subagent": "This starts a second agent run.",
  "tool.memory_write": "This saves a note the agent will see in later sessions.",
  "tool.message_send": "This sends a message to another agent.",
  "tool.swarm_dispatch": "This hands work to another agent.",
  "tool.schedule_create": "This schedules work to run later, without asking again.",
  "tool.schedule_cancel": "This cancels scheduled work.",
  "tool.task_create": "This starts work that keeps running in the background.",
  "tool.task_stop": "This stops background work.",
  "tool.read_file": "This reads a file in your workspace.",
  "tool.glob_files": "This lists files in your workspace.",
  "tool.search_files": "This searches your workspace for a file.",
  "tool.grep": "This searches the contents of files in your workspace.",
};
