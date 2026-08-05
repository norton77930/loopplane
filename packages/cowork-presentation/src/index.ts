/**
 * @loopplane/cowork-presentation — first-party shared presentation surface (078).
 *
 * Transport-neutral exports for Web and Desktop adapters. US4 (T061+) moves
 * chat/shell/settings components here; this file is the scaffold entrypoint only.
 */

/** Package identity for workspace resolution smoke checks. */
export const COWORK_PRESENTATION_PACKAGE = "@loopplane/cowork-presentation" as const;

/** Scaffold marker: non-empty public surface before component extraction. */
export const COWORK_PRESENTATION_SCAFFOLD = true as const;
