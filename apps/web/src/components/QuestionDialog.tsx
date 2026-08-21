import { QuestionDialog as SharedQuestionDialog, type QuestionDialogProps } from "@loopplane/cowork-presentation";
export type { QuestionDialogProps as Props } from "@loopplane/cowork-presentation";
export function QuestionDialog(props: QuestionDialogProps) { return <SharedQuestionDialog {...props} />; }
