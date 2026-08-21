/**
 * Multi-pane presentation state machine (078 T051).
 *
 * Enforces: unique pane ids, session dedup focus, one lease owner, pane-local drafts.
 */

import type {
  PaneId,
  PaneState,
  PaneWorkspaceState,
} from "./types";

export function createEmptyWorkspace(): PaneWorkspaceState {
  return {
    panes: [],
    focusedPaneId: null,
    leaseOwnerPaneId: null,
    order: [],
  };
}

export function openPane(
  state: PaneWorkspaceState,
  input: {
    paneId: PaneId;
    sessionId?: string | null;
    title?: string;
  },
): PaneWorkspaceState {
  // Same session: focus existing pane instead of duplicating (V1).
  if (input.sessionId) {
    const existing = state.panes.find((p) => p.sessionId === input.sessionId);
    if (existing) {
      return focusPane(state, existing.paneId);
    }
  }
  if (state.panes.some((p) => p.paneId === input.paneId)) {
    return focusPane(state, input.paneId);
  }
  const pane: PaneState = {
    paneId: input.paneId,
    sessionId: input.sessionId ?? null,
    title: input.title ?? input.sessionId?.slice(0, 8) ?? "Untitled",
    mode: "read_only",
    draft: { text: "" },
    focused: true,
    leaseOwner: false,
  };
  const panes = state.panes.map((p) => ({ ...p, focused: false })).concat(pane);
  return {
    panes,
    focusedPaneId: pane.paneId,
    leaseOwnerPaneId: state.leaseOwnerPaneId,
    order: state.order.concat(pane.paneId),
  };
}

export function focusPane(
  state: PaneWorkspaceState,
  paneId: PaneId,
): PaneWorkspaceState {
  if (!state.panes.some((p) => p.paneId === paneId)) return state;
  return {
    ...state,
    focusedPaneId: paneId,
    panes: state.panes.map((p) => ({
      ...p,
      focused: p.paneId === paneId,
      // Focusing a non-owner pane keeps it read-only.
      mode:
        state.leaseOwnerPaneId === p.paneId ? "interactive" : "read_only",
    })),
  };
}

export function setPaneDraft(
  state: PaneWorkspaceState,
  paneId: PaneId,
  text: string,
): PaneWorkspaceState {
  return {
    ...state,
    panes: state.panes.map((p) =>
      p.paneId === paneId ? { ...p, draft: { text } } : p,
    ),
  };
}

/**
 * Claim interactive lease for a pane. Fails (returns same state + ok:false)
 * when another pane already owns the lease.
 */
export function claimLease(
  state: PaneWorkspaceState,
  paneId: PaneId,
): { state: PaneWorkspaceState; ok: boolean; ownerPaneId: string | null } {
  const pane = state.panes.find((p) => p.paneId === paneId);
  if (!pane) {
    return { state, ok: false, ownerPaneId: state.leaseOwnerPaneId };
  }
  if (state.leaseOwnerPaneId && state.leaseOwnerPaneId !== paneId) {
    return {
      state,
      ok: false,
      ownerPaneId: state.leaseOwnerPaneId,
    };
  }
  const next: PaneWorkspaceState = {
    ...state,
    leaseOwnerPaneId: paneId,
    focusedPaneId: paneId,
    panes: state.panes.map((p) => {
      if (p.paneId === paneId) {
        return {
          ...p,
          leaseOwner: true,
          mode: "interactive",
          focused: true,
        };
      }
      return {
        ...p,
        leaseOwner: false,
        mode: "read_only",
        focused: false,
      };
    }),
  };
  return { state: next, ok: true, ownerPaneId: paneId };
}

export function releaseLease(
  state: PaneWorkspaceState,
  paneId?: PaneId,
): PaneWorkspaceState {
  if (paneId && state.leaseOwnerPaneId && state.leaseOwnerPaneId !== paneId) {
    return state;
  }
  return {
    ...state,
    leaseOwnerPaneId: null,
    panes: state.panes.map((p) => ({
      ...p,
      leaseOwner: false,
      mode: "read_only" as const,
    })),
  };
}

export function closePane(
  state: PaneWorkspaceState,
  paneId: PaneId,
): PaneWorkspaceState {
  const panes = state.panes.filter((p) => p.paneId !== paneId);
  const order = state.order.filter((id) => id !== paneId);
  let leaseOwnerPaneId = state.leaseOwnerPaneId;
  if (leaseOwnerPaneId === paneId) {
    leaseOwnerPaneId = null;
  }
  let focusedPaneId = state.focusedPaneId;
  if (focusedPaneId === paneId) {
    focusedPaneId = order[order.length - 1] ?? null;
  }
  return {
    panes: panes.map((p) => ({
      ...p,
      focused: p.paneId === focusedPaneId,
      leaseOwner: p.paneId === leaseOwnerPaneId,
      mode: p.paneId === leaseOwnerPaneId ? "interactive" : "read_only",
    })),
    order,
    focusedPaneId,
    leaseOwnerPaneId,
  };
}

export function canSubmitFromPane(state: PaneWorkspaceState, paneId: PaneId): boolean {
  return state.leaseOwnerPaneId === paneId;
}

export function getFocusedPane(state: PaneWorkspaceState): PaneState | null {
  if (!state.focusedPaneId) return null;
  return state.panes.find((p) => p.paneId === state.focusedPaneId) ?? null;
}
