import { useId, useState } from "react";

import type { ConversationEntry } from "../state/chat";

type ToolEntry = Extract<ConversationEntry, { kind: "tool" }>;

// An inline, collapsible tool card (FR-002): the tool name + a status that moves from
// running (no outcome yet) to success/failure. Consecutive cards group readably while each
// stays independently inspectable (FR-003).
export function ToolCard({
  entry,
  onAttachReference,
}: {
  entry: ToolEntry;
  onAttachReference?: (reference: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  const state = entry.outcome ?? "running";

  return (
    <div className="tool-card" data-open={open} data-testid="tool-card">
      <button
        type="button"
        className="tool-card-header"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="caret" aria-hidden="true">&#9656;</span>
        <span className="tool-name">{entry.name}</span>
        <span className="tool-status" data-state={state}>
          <span className="tool-status-dot" aria-hidden="true" />
          {state}
        </span>
      </button>
      {entry.artifactReference && (
        <div className="tool-reference" aria-label="Artifact reference">
          <code>{entry.artifactReference}</code>
          {onAttachReference && (
            <button
              type="button"
              onClick={() => onAttachReference(entry.artifactReference as string)}
            >
              Attach reference
            </button>
          )}
        </div>
      )}
      {open && (
        <div
          id={detailId}
          className="tool-detail"
          role="region"
          aria-label={`${entry.name} tool details`}
        >
          Call <code>{entry.callId}</code> &mdash; {state}
        </div>
      )}
    </div>
  );
}
