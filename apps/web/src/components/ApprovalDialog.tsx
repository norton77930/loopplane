import type { ApprovalDecision } from "../api/client";
import { Modal } from "./Modal";

// A styled approval dialog (FR-004) presented as a true modal (032): allow (scope "once"), deny,
// and "always allow for this session". Esc resolves to the safe default — **deny** — never an
// implicit allow (FR-002).
interface Props {
  toolName: string;
  onDecide: (decision: ApprovalDecision) => void;
}

export function ApprovalDialog({ toolName, onDecide }: Props) {
  return (
    <Modal onClose={() => onDecide({ allow: false })} label="approval request">
      <div
        className="dialog dialog-approval"
        data-testid="approval"
        role="group"
        aria-label="approval request"
      >
        <div className="dialog-prompt">Approve tool {toolName}?</div>
        <div className="dialog-actions">
          <button
            type="button"
            className="primary"
            onClick={() => onDecide({ allow: true, scope: "once" })}
          >
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
    </Modal>
  );
}
