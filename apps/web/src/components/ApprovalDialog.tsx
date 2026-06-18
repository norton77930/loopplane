import type { ApprovalDecision } from "../api/client";

// A styled, in-flow approval dialog (FR-004): allow (scope "once"), deny, and an
// "always allow for this session" choice mapped onto the existing decision scope (research R4).
interface Props {
  toolName: string;
  onDecide: (decision: ApprovalDecision) => void;
}

export function ApprovalDialog({ toolName, onDecide }: Props) {
  return (
    <div className="dialog dialog-approval" data-testid="approval" role="group" aria-label="approval request">
      <div className="dialog-prompt">Approve tool {toolName}?</div>
      <div className="dialog-actions">
        <button type="button" className="primary" onClick={() => onDecide({ allow: true, scope: "once" })}>
          Allow
        </button>
        <button type="button" className="danger" onClick={() => onDecide({ allow: false })}>
          Deny
        </button>
        <button type="button" onClick={() => onDecide({ allow: true, scope: "session" })}>
          Always allow this session
        </button>
      </div>
    </div>
  );
}
