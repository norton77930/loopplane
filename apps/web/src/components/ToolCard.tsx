import { useState } from "react";

import type { ConversationEntry } from "../state/chat";

type ToolEntry = Extract<ConversationEntry, { kind: "tool" }>;

// An inline, collapsible tool card (FR-002): the tool name + a status that moves from
// running (no outcome yet) to success/failure. Consecutive cards group readably while each
// stays independently inspectable (FR-003).
export function ToolCard({ entry }: { entry: ToolEntry }) {
  const [open, setOpen] = useState(false);
  const state = entry.outcome ?? "running";

  return (
    <div className="tool-card" data-open={open} data-testid="tool-card">
      <button
        type="button"
        className="tool-card-header"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="caret" aria-hidden="true">&#9656;</span>
        <span className="tool-name">{entry.name}</span>
        <span className="tool-status" data-state={state}>{state}</span>
      </button>
      {open && (
        <div className="tool-detail">
          Call <code>{entry.callId}</code> &mdash; {state}
        </div>
      )}
    </div>
  );
}
