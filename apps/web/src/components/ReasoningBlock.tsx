import { useState } from "react";

// A distinct, de-emphasized, collapsible thinking block (FR-001/002). Renders streamed reasoning
// as pre-wrapped text, visually separate from the markdown answer. Nothing renders for empty text
// (graceful — a turn with no reasoning shows no block).
export function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(true);
  if (!text) return null;

  return (
    <div className="reasoning-block" data-testid="reasoning" data-open={open}>
      <button
        type="button"
        className="reasoning-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="caret" aria-hidden="true">&#9656;</span> Thinking
      </button>
      {open && <div className="reasoning-text">{text}</div>}
    </div>
  );
}
