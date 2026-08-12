import { useEffect, useRef, useState } from "react";

import { dismissOnEscape, focusElement, restoreFocus } from "../focus";

export type QuestionDialogProps = {
  prompt: string;
  options: string[];
  onAnswer: (answers: string[]) => void;
  onClose?: () => void;
  returnFocus?: HTMLElement | null;
  fallbackFocus?: HTMLElement | null;
};

/** Transport-neutral question dialog with keyboard dismissal and focus return. */
export function QuestionDialog({
  prompt,
  options,
  onAnswer,
  onClose,
  returnFocus,
  fallbackFocus,
}: QuestionDialogProps) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasOptions = options.length > 0;

  useEffect(() => {
    focusElement(inputRef.current);
  }, []);

  function close() {
    onClose?.();
    restoreFocus(returnFocus, fallbackFocus);
  }

  function submit() {
    const answers = hasOptions ? selected : [text];
    if (hasOptions && answers.length === 0) return;
    onAnswer(answers);
    restoreFocus(returnFocus, fallbackFocus);
  }

  return (
    <div className="modal-backdrop" onClick={close}>
      <form
        className="modal dialog cowork-dialog cowork-question-dialog"
        data-testid="question"
        role="dialog"
        aria-modal="true"
        aria-label="Question"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        onKeyDown={(event) => {
          dismissOnEscape(event, close, returnFocus, fallbackFocus);
        }}
      >
        <p>{prompt}</p>
        {hasOptions ? (
          <div className="cowork-dialog-options">
            {options.map((option, index) => (
              <label key={option}>
                <input
                  ref={index === 0 ? inputRef : undefined}
                  type="checkbox"
                  checked={selected.includes(option)}
                  onChange={() => {
                    setSelected((current) =>
                      current.includes(option)
                        ? current.filter((candidate) => candidate !== option)
                        : [...current, option],
                    );
                  }}
                />
                {option}
              </label>
            ))}
          </div>
        ) : (
          <input
            ref={inputRef}
            type="text"
            aria-label="answer"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        )}
        <div className="cowork-dialog-actions">
          <button type="submit">Send</button>
        </div>
      </form>
    </div>
  );
}
