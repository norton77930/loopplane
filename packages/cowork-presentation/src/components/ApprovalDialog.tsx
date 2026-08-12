import { useEffect, useRef } from "react";

import { dismissOnEscape, focusElement, restoreFocus } from "../focus";

export type ApprovalDecision =
  | { allow: false }
  | { allow: true; scope: "once" | "session" };

export type ApprovalDialogProps = {
  toolName: string;
  onDecide: (decision: ApprovalDecision) => void;
  returnFocus?: HTMLElement | null;
  fallbackFocus?: HTMLElement | null;
};

/** Transport-neutral approval dialog with an explicit safe Escape decision. */
export function ApprovalDialog({
  toolName,
  onDecide,
  returnFocus,
  fallbackFocus,
}: ApprovalDialogProps) {
  const allowRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    focusElement(allowRef.current);
  }, []);

  function decide(decision: ApprovalDecision) {
    onDecide(decision);
    restoreFocus(returnFocus, fallbackFocus);
  }

  return (
    <div className="modal-backdrop" onClick={() => decide({ allow: false })}>
      <div
        className="modal dialog cowork-dialog cowork-approval-dialog"
        data-testid="approval"
        role="dialog"
        aria-modal="true"
        aria-label="Approval request"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          dismissOnEscape(event, () => onDecide({ allow: false }), returnFocus, fallbackFocus);
        }}
      >
        <p>Approve tool {toolName}?</p>
        <div className="cowork-dialog-actions">
          <button ref={allowRef} type="button" onClick={() => decide({ allow: true, scope: "once" })}>
            Allow
          </button>
          <button type="button" onClick={() => decide({ allow: false })}>
            Deny
          </button>
          <button type="button" onClick={() => decide({ allow: true, scope: "session" })}>
            Always allow this session
          </button>
        </div>
      </div>
    </div>
  );
}
