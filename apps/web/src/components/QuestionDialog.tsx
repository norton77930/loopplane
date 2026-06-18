import { useState } from "react";

// A styled, in-flow question dialog (FR-005): a single free-text answer, matching the current
// event contract (the answer is sent as a single-element array by the App).
interface Props {
  prompt: string;
  onAnswer: (text: string) => void;
}

export function QuestionDialog({ prompt, onAnswer }: Props) {
  const [value, setValue] = useState("");
  return (
    <form
      className="dialog dialog-question"
      data-testid="question"
      onSubmit={(event) => {
        event.preventDefault();
        onAnswer(value);
      }}
    >
      <div className="dialog-prompt">{prompt}</div>
      <div className="dialog-actions">
        <input
          type="text"
          aria-label="answer"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <button type="submit" className="primary">
          Send
        </button>
      </div>
    </form>
  );
}
