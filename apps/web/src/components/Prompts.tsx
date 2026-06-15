import type { FormEvent } from "react";

import type { ChatState } from "../state/chat";

interface Props {
  state: ChatState;
  onApproval: (requestId: string, allow: boolean) => void;
  onQuestion: (requestId: string, answer: string) => void;
}

export function Prompts({ state, onApproval, onQuestion }: Props) {
  if (state.pendingApproval) {
    const { requestId, toolName } = state.pendingApproval;
    return (
      <div className="prompt prompt-approval" data-testid="approval">
        <span>Approve tool {toolName}?</span>
        <button type="button" onClick={() => onApproval(requestId, true)}>
          Allow
        </button>
        <button type="button" onClick={() => onApproval(requestId, false)}>
          Deny
        </button>
      </div>
    );
  }

  if (state.pendingQuestion) {
    const { requestId, prompt } = state.pendingQuestion;
    const submit = (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const field = event.currentTarget.elements.namedItem(
        "answer",
      ) as HTMLInputElement;
      onQuestion(requestId, field.value);
    };
    return (
      <form className="prompt prompt-question" data-testid="question" onSubmit={submit}>
        <span>{prompt}</span>
        <input name="answer" aria-label="answer" />
        <button type="submit">Send</button>
      </form>
    );
  }

  return null;
}
