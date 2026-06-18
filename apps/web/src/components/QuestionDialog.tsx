import { useState } from "react";

// A styled, in-flow question dialog (FR-003/004/005). When the question carries options, render
// them as a select-one-or-many choice group and submit the selection as answers; when it carries
// none, fall back to the unit-025 free-text field. The wire `answers` is already a list, so a
// single selection submits a single-element array.
interface Props {
  prompt: string;
  options: string[];
  onAnswer: (answers: string[]) => void;
}

export function QuestionDialog({ prompt, options, onAnswer }: Props) {
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
  );
}
