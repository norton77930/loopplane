/**
 * Multi-pane presentation types (078 T051).
 *
 * Pure view-model types: no transport, Host, or path authority.
 */

export type PaneId = string;

export type PaneMode = "interactive" | "read_only";

export type PaneDraft = {
  /** Renderer-transient unsent text; never durable authority. */
  text: string;
};

export type PaneState = {
  paneId: PaneId;
  sessionId: string | null;
  title: string;
  mode: PaneMode;
  draft: PaneDraft;
  focused: boolean;
  /** True when this pane holds the profile interactive lease. */
  leaseOwner: boolean;
};

export type PaneWorkspaceState = {
  panes: PaneState[];
  /** Focused pane id; may be read-only while another owns the lease. */
  focusedPaneId: PaneId | null;
  /** At most one interactive lease owner pane. */
  leaseOwnerPaneId: PaneId | null;
  order: PaneId[];
};
