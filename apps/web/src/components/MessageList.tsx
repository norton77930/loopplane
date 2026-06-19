import { useEffect, useRef, useState } from "react";

import { useTranslation } from "../i18n/i18n";
import { copyText } from "../lib/clipboard";
import type { ConversationEntry } from "../state/chat";
import { Markdown } from "./Markdown";
import { ReasoningBlock } from "./ReasoningBlock";
import { ToolCard } from "./ToolCard";

const BOTTOM_THRESHOLD = 40;

// The scrolling message region: renders the ordered entries (FR-001/002/006) and owns its
// own scroll container so it can auto-scroll when pinned to the bottom and offer a
// jump-to-latest affordance when the user has scrolled up (FR-011). Each user/assistant message
// carries copy + regenerate actions (unit 031); regenerate shows on the latest assistant message.
interface Props {
  entries: ConversationEntry[];
  onRegenerate?: () => void;
  canRegenerate?: boolean;
}

export function MessageList({ entries, onRegenerate, canRegenerate }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  let lastAssistant = -1;
  entries.forEach((entry, index) => {
    if (entry.kind === "assistant") lastAssistant = index;
  });

  function onScroll() {
    const el = ref.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_THRESHOLD;
    setPinned(atBottom);
  }

  useEffect(() => {
    if (pinned && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [entries, pinned]);

  function jumpToLatest() {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setPinned(true);
  }

  return (
    <div className="messages" data-testid="messages" ref={ref} onScroll={onScroll}>
      {entries.map((entry, index) => (
        <Entry
          key={index}
          entry={entry}
          onRegenerate={index === lastAssistant ? onRegenerate : undefined}
          canRegenerate={canRegenerate}
        />
      ))}
      {!pinned && (
        <button type="button" className="jump-latest" onClick={jumpToLatest}>
          Jump to latest
        </button>
      )}
    </div>
  );
}

interface EntryProps {
  entry: ConversationEntry;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
}

function Entry({ entry, onRegenerate, canRegenerate }: EntryProps) {
  switch (entry.kind) {
    case "user":
      return (
        <div className="message message-user">
          <div className="message-role">You</div>
          <div className="bubble">{entry.text}</div>
          <MessageActions text={entry.text} />
        </div>
      );
    case "reasoning":
      return <ReasoningBlock text={entry.text} />;
    case "assistant":
      return (
        <div className="message message-assistant">
          <div className="message-role">LoopPlane</div>
          <Markdown>{entry.text}</Markdown>
          <MessageActions
            text={entry.text}
            onRegenerate={onRegenerate}
            canRegenerate={canRegenerate}
          />
        </div>
      );
    case "tool":
      return <ToolCard entry={entry} />;
    case "terminated":
      return (
        <div className="terminated-marker">
          Run ended &mdash; <span className="reason">{entry.reason}</span> ({entry.turns} turn
          {entry.turns === 1 ? "" : "s"})
        </div>
      );
  }
}

function MessageActions({
  text,
  onRegenerate,
  canRegenerate,
}: {
  text: string;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="message-actions">
      <button type="button" onClick={() => void copyText(text)}>
        {t("action.copy")}
      </button>
      {onRegenerate && (
        <button
          type="button"
          disabled={canRegenerate === false}
          onClick={onRegenerate}
        >
          {t("action.regenerate")}
        </button>
      )}
    </div>
  );
}
