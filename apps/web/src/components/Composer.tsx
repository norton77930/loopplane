import { useRef, useState, type ReactNode } from "react";

// A sticky composer (FR-012): a textarea that grows with multi-line content and disables
// sending while a run is in flight. Enter sends; Shift+Enter inserts a newline. `extras` hosts
// the composer controls (the model selector + attachments, unit 028).
interface Props {
  disabled: boolean;
  onSend: (text: string) => void;
  extras?: ReactNode;
}

const MAX_HEIGHT = 200;

export function Composer({ disabled, onSend, extras }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function grow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  }

  return (
    <div className="composer-area">
      {extras ? <div className="composer-extras">{extras}</div> : null}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <textarea
        ref={ref}
        aria-label="prompt"
        rows={1}
        value={value}
        disabled={disabled}
        placeholder="Message LoopPlane..."
        onChange={(event) => {
          setValue(event.target.value);
          grow();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
        <button type="submit" className="primary" disabled={disabled || !value.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
