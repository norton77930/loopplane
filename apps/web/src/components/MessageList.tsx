import { useEffect, useRef, useState } from "react";

import { useTranslation } from "../i18n/i18n";
import { copyText } from "../lib/clipboard";
import type { ConversationEntry } from "../state/chat";
import { Markdown } from "./Markdown";
import { ReasoningBlock } from "./ReasoningBlock";
import { Skeleton } from "./Skeleton";
import { ToolCard } from "./ToolCard";

const BOTTOM_THRESHOLD = 40;
const EXAMPLES = [
  "Summarize the attached file",
  "Explain what this project does",
  "List the available tools",
];

// The scrolling message region (FR-001/002/006/011) + unit-031 per-message actions + unit-032
// loading skeleton and a richer first-run empty state with example prompts.
interface Props {
  entries: ConversationEntry[];
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  onExample?: (prompt: string) => void;
  onFork?: (sequence: number) => void;
  onAttachReference?: (reference: string) => void;
  loading?: boolean;
}

export function MessageList({
  entries,
  onRegenerate,
  canRegenerate,
  onExample,
  onFork,
  onAttachReference,
  loading,
}: Props) {
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
    <div
      className="messages"
      data-testid="messages"
      role="log"
      aria-label="Conversation"
      aria-live="polite"
      aria-atomic="false"
      aria-relevant="additions"
      ref={ref}
      onScroll={onScroll}
    >
      {loading && entries.length === 0 ? (
        <Skeleton />
      ) : entries.length === 0 ? (
        <EmptyState onExample={onExample} />
      ) : (
        entries.map((entry, index) => (
          <Entry
            key={index}
            entry={entry}
            onRegenerate={index === lastAssistant ? onRegenerate : undefined}
            canRegenerate={canRegenerate}
            onFork={onFork ? () => onFork(index + 1) : undefined}
            onAttachReference={onAttachReference}
          />
        ))
      )}
      {!pinned && (
        <button type="button" className="jump-latest" onClick={jumpToLatest}>
          Jump to latest
        </button>
      )}
    </div>
  );
}

function EmptyState({ onExample }: { onExample?: (prompt: string) => void }) {
  const { t } = useTranslation();
  return (
    <div className="empty-state">
      <h2 className="empty-title">{t("empty.title")}</h2>
      <p className="empty-description">
        Ask about your workspace, attach a file, or choose a starting point.
      </p>
      <div className="empty-examples">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="example-chip"
            onClick={() => onExample?.(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

interface EntryProps {
  entry: ConversationEntry;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  onFork?: () => void;
  onAttachReference?: (reference: string) => void;
}

function Entry({
  entry,
  onRegenerate,
  canRegenerate,
  onFork,
  onAttachReference,
}: EntryProps) {
  switch (entry.kind) {
    case "user":
      return (
        <article className="message message-user" data-kind="user" aria-label="You message">
          <div className="message-role">You</div>
          <div className="bubble">{entry.text}</div>
          <MessageActions text={entry.text} onFork={onFork} />
        </article>
      );
    case "reasoning":
      return <ReasoningBlock text={entry.text} />;
    case "assistant":
      return (
        <article
          className="message message-assistant"
          data-kind="assistant"
          aria-label="LoopPlane message"
        >
          <div className="message-role">LoopPlane</div>
          <Markdown>{entry.text}</Markdown>
          <MessageActions
            text={entry.text}
            onRegenerate={onRegenerate}
            canRegenerate={canRegenerate}
            onFork={onFork}
          />
        </article>
      );
    case "tool":
      return <ToolCard entry={entry} onAttachReference={onAttachReference} />;
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
  onFork,
}: {
  text: string;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  onFork?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="message-actions">
      <button type="button" onClick={() => void copyText(text)}>
        {t("action.copy")}
      </button>
      {onFork && (
        <button type="button" onClick={onFork}>
          Fork
        </button>
      )}
      {onRegenerate && (
        <button type="button" disabled={canRegenerate === false} onClick={onRegenerate}>
          {t("action.regenerate")}
        </button>
      )}
    </div>
  );
}
