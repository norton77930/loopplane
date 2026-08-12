import { ApprovalDialog as SharedApprovalDialog, type ApprovalDialogProps } from "@loopplane/cowork-presentation";
export type { ApprovalDecision, ApprovalDialogProps as Props } from "@loopplane/cowork-presentation";
export function ApprovalDialog(props: ApprovalDialogProps) { return <SharedApprovalDialog {...props} />; }
