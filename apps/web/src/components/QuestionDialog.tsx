import { useState } from "react";

import { Modal } from "./Modal";

// A styled question dialog (FR-003/004/005) presented as a true modal (032). Options render as a
// select-one-or-many choice group (free-text fallback when there are none). Esc cancels — it
// dismisses the dialog via onClose without submitting an answer (FR-002).
interface Props {
  prompt: string;
  options: string[];
  onAnswer: (answers: string[]) => void;
  onClose?: () => void;
}

export function QuestionDialog({ prompt, options, onAnswer, onClose }: Props) {
  const hasOptions = options.length > 0;
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(option: string) {
    setSelected((current) =>
      current.includes(option) ? current.filter((o) => o !== option) : [...current, option],
    );
  }

  function submit() {
    if (hasOptions) {
      if (selected.length > 0) onAnswer(selected);
    } else {
      onAnswer([text]);
    }
  }

  return (
    <Modal onClose={() => onClose?.()} label="question">
      <form
        className="dialog dialog-question"
        data-testid="question"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="dialog-prompt">{prompt}</div>
        {hasOptions ? (
          <div className="dialog-options">
            {options.map((option) => (
              <label key={option} className="option-choice">
                <input
                  type="checkbox"
                  checked={selected.includes(option)}
                  onChange={() => toggle(option)}
                />
                {option}
              </label>
            ))}
          </div>
        ) : (
          <input
            type="text"
            aria-label="answer"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        )}
        <div className="dialog-actions">
          <button type="submit" className="primary">
            Send
          </button>
        </div>
      </form>
    </Modal>
  );
}
