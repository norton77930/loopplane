import { useEffect, useRef } from "react";

import { dismissOnEscape, focusElement, restoreFocus } from "../focus";
import { useTranslation } from "../i18n/i18n";
import { toolConsequence } from "../vocabulary";

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
  const { t } = useTranslation();
  const consequenceKey = toolConsequence(toolName);

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
        {/* The tool's own name stays visible — someone who knows the runtime
            should not have to work out which tool this is — but it is no longer
            the whole question. */}
        <p className="cowork-approval-question">
          {t("approval.question")} <code>{toolName}</code>?
        </p>
        {consequenceKey && (
          <p className="cowork-approval-consequence">{t(consequenceKey)}</p>
        )}
        <div className="cowork-dialog-actions">
          <button ref={allowRef} type="button" onClick={() => decide({ allow: true, scope: "once" })}>
            {t("approval.allow")}
          </button>
          <button type="button" onClick={() => decide({ allow: false })}>
            {t("approval.deny")}
          </button>
          <button type="button" onClick={() => decide({ allow: true, scope: "session" })}>
            {t("approval.alwaysAllow")}
          </button>
        </div>
      </div>
    </div>
  );
}
