/**
 * Multi-pane cowork shell (078 T053).
 *
 * Presentation-only: parent supplies pane state and action callbacks.
 */

import { useRef, type KeyboardEvent, type ReactNode } from "react";

export const PACKAGED_SMOKE_SUCCESS_MARKER = "loopplane-packaged-smoke-ok";

import { focusElement } from "../focus";
import { getFocusedPane } from "../panes/state";
import type { PaneWorkspaceState } from "../panes/types";

export type CoworkShellProps = {
  workspace: PaneWorkspaceState;
  leftSidebar?: ReactNode;
  rightSidebar?: ReactNode;
  children: ReactNode;
  onFocusPane: (paneId: string) => void;
  onClosePane: (paneId: string) => void;
  onRequestInteractive: (paneId: string) => void;
  /** When true, closing lease owner requires confirmation. */
  ownerCloseNeedsConfirm?: boolean;
  onConfirmOwnerClose?: (paneId: string) => void;
};

export function CoworkShell({
  workspace,
  leftSidebar,
  rightSidebar,
  children,
  onFocusPane,
  onClosePane,
  onRequestInteractive,
  ownerCloseNeedsConfirm = true,
  onConfirmOwnerClose,
}: CoworkShellProps) {
  const focused = getFocusedPane(workspace);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const paneIds = workspace.order.filter((paneId) =>
    workspace.panes.some((pane) => pane.paneId === paneId),
  );

  function onPaneKeyDown(event: KeyboardEvent<HTMLButtonElement>, paneId: string) {
    const currentIndex = paneIds.indexOf(paneId);
    if (currentIndex === -1) return;

    let nextIndex: number | undefined;
    switch (event.key) {
      case "ArrowRight":
        nextIndex = (currentIndex + 1) % paneIds.length;
        break;
      case "ArrowLeft":
        nextIndex = (currentIndex - 1 + paneIds.length) % paneIds.length;
        break;
      case "Home":
        nextIndex = 0;
        break;
      case "End":
        nextIndex = paneIds.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const nextPaneId = paneIds[nextIndex];
    onFocusPane(nextPaneId);
    focusElement(tabRefs.current[nextPaneId]);
  }

  return (
    <div className="cowork-shell" data-testid="cowork-shell">
      {leftSidebar}
      <div className="cowork-center">
        <div
          className="pane-tabs"
          role="tablist"
          aria-label="Open sessions"
        >
          {workspace.order.map((paneId) => {
            const pane = workspace.panes.find((p) => p.paneId === paneId);
            if (!pane) return null;
            const selected = workspace.focusedPaneId === paneId;
            return (
              <div key={paneId} className="pane-tab" role="presentation">
                <button
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  data-mode={pane.mode}
                  data-lease-owner={pane.leaseOwner ? "true" : "false"}
                  className={selected ? "selected" : undefined}
                  tabIndex={selected ? 0 : -1}
                  ref={(element) => {
                    tabRefs.current[paneId] = element;
                  }}
                  onClick={() => onFocusPane(paneId)}
                  onKeyDown={(event) => onPaneKeyDown(event, paneId)}
                >
                  {pane.leaseOwner ? "● " : ""}
                  {pane.title}
                  {pane.mode === "read_only" ? " (read-only)" : ""}
                </button>
                <button
                  type="button"
                  aria-label={`Close ${pane.title}`}
                  onClick={() => {
                    if (
                      pane.leaseOwner &&
                      ownerCloseNeedsConfirm &&
                      onConfirmOwnerClose
                    ) {
                      onConfirmOwnerClose(paneId);
                      return;
                    }
                    onClosePane(paneId);
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
        {focused && focused.mode === "read_only" && (
          <div className="pane-banner" role="status">
            This pane is read-only.
            {workspace.leaseOwnerPaneId &&
              workspace.leaseOwnerPaneId !== focused.paneId && (
                <> Another pane holds the active interaction.</>
              )}{" "}
            <button
              type="button"
              onClick={() => onRequestInteractive(focused.paneId)}
            >
              Make interactive
            </button>
          </div>
        )}
        <div
          className="pane-body"
          data-pane-id={focused?.paneId ?? ""}
          aria-label="LoopPlane smoke latest outcome"
          role="group"
        >
          {children}
        </div>
      </div>
      {rightSidebar}
    </div>
  );
}
