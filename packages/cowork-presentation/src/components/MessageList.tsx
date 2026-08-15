import { useEffect, useId, useRef, useState, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { useTranslation } from "../i18n/i18n";
import type { ConversationEntry } from "../state/chat";

const BOTTOM_THRESHOLD = 40;
/** Web's starter prompts; a host with different affordances passes its own. */
const EXAMPLES = [
  "Summarize the attached file",
  "Explain what this project does",
  "List the available tools",
];
const EMPTY_HINT =
  "Ask about your workspace, attach a file, or choose a starting point.";

export interface MessageListProps {
  entries: ConversationEntry[];
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  onExample?: (prompt: string) => void;
  onFork?: (sequence: number) => void;
  onAttachReference?: (reference: string) => void;
  loading?: boolean;
  /**
   * Starter prompts for the empty state. Defaults to Web's set, which offers to
   * summarize an attachment — a host without an attach control passes its own
   * rather than showing a chip for something the user cannot do.
   */
  examples?: readonly string[];
  /** The line under the empty-state title. Defaults to Web's copy. */
  emptyHint?: string;
}

export function MessageList({
  entries,
  onRegenerate,
  canRegenerate,
  onExample,
  onFork,
  onAttachReference,
  loading,
  examples = EXAMPLES,
  emptyHint = EMPTY_HINT,
}: MessageListProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);
  let lastAssistant = -1;
  entries.forEach((entry, index) => {
    if (entry.kind === "assistant") lastAssistant = index;
  });

  function onScroll() {
    const element = ref.current;
    if (!element) return;
    setPinned(element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD);
  }

  useEffect(() => {
    if (pinned && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [entries, pinned]);

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
      {loading && entries.length === 0 ? <Skeleton /> : entries.length === 0 ? (
        <EmptyState onExample={onExample} examples={examples} hint={emptyHint} />
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
      {!pinned ? (
        <button
          type="button"
          className="jump-latest"
          onClick={() => {
            if (!ref.current) return;
            ref.current.scrollTop = ref.current.scrollHeight;
            setPinned(true);
          }}
        >
          Jump to latest
        </button>
      ) : null}
    </div>
  );
}

function EmptyState({
  onExample,
  examples,
  hint,
}: {
  onExample?: (prompt: string) => void;
  examples: readonly string[];
  hint: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="empty-state">
      <h2 className="empty-title">{t("empty.title")}</h2>
      <p className="empty-description">{hint}</p>
      {/* A chip with no handler is a button that does nothing, so a host that
          does not wire `onExample` gets no chips rather than dead ones. */}
      {onExample && (
        <div className="empty-examples">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              className="example-chip"
              onClick={() => onExample(example)}
            >
              {example}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Entry({
  entry,
  onRegenerate,
  canRegenerate,
  onFork,
  onAttachReference,
}: {
  entry: ConversationEntry;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  onFork?: () => void;
  onAttachReference?: (reference: string) => void;
}) {
  switch (entry.kind) {
    case "user":
      return <article className="message message-user" data-kind="user" aria-label="You message"><div className="message-role">You</div><div className="bubble">{entry.text}</div><MessageActions text={entry.text} onFork={onFork} /></article>;
    case "reasoning":
      return <ReasoningBlock text={entry.text} />;
    case "assistant":
      return <article className="message message-assistant" data-kind="assistant" aria-label="LoopPlane message"><div className="message-role">LoopPlane</div><Markdown>{entry.text}</Markdown><MessageActions text={entry.text} onRegenerate={onRegenerate} canRegenerate={canRegenerate} onFork={onFork} /></article>;
    case "tool":
      return <ToolCard entry={entry} onAttachReference={onAttachReference} />;
    case "terminated":
      return <div className="terminated-marker">Run ended &mdash; <span className="reason">{entry.reason}</span> ({entry.turns} turn{entry.turns === 1 ? "" : "s"})</div>;
  }
}

function MessageActions({ text, onRegenerate, canRegenerate, onFork }: { text: string; onRegenerate?: () => void; canRegenerate?: boolean; onFork?: () => void }) {
  const { t } = useTranslation();
  return <div className="message-actions">
    <button type="button" onClick={() => void copyText(text)}>{t("action.copy")}</button>
    {onFork ? <button type="button" onClick={onFork}>Fork</button> : null}
    {onRegenerate ? <button type="button" disabled={canRegenerate === false} onClick={onRegenerate}>{t("action.regenerate")}</button> : null}
  </div>;
}

function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(true);
  const detailId = useId();
  if (!text) return null;
  return <div className="reasoning-block" data-testid="reasoning" data-open={open}>
    <button type="button" className="reasoning-toggle" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen((value) => !value)}><span className="caret" aria-hidden="true">▶</span> Thinking</button>
    {open ? <div id={detailId} className="reasoning-text" role="region" aria-label="Reasoning details">{text}</div> : null}
  </div>;
}

function ToolCard({ entry, onAttachReference }: { entry: Extract<ConversationEntry, { kind: "tool" }>; onAttachReference?: (reference: string) => void }) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  const state = entry.outcome ?? "running";
  return <div className="tool-card" data-open={open} data-testid="tool-card">
    <button type="button" className="tool-card-header" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen((value) => !value)}><span className="caret" aria-hidden="true">▶</span><span className="tool-name">{entry.name}</span><span className="tool-status" data-state={state}><span className="tool-status-dot" aria-hidden="true" />{state}</span></button>
    {entry.artifactReference ? <div className="tool-reference" aria-label="Artifact reference"><code>{entry.artifactReference}</code>{onAttachReference ? <button type="button" onClick={() => onAttachReference(entry.artifactReference as string)}>Attach reference</button> : null}</div> : null}
    {open ? <div id={detailId} className="tool-detail" role="region" aria-label={`${entry.name} tool details`}>Call <code>{entry.callId}</code> &mdash; {state}</div> : null}
  </div>;
}

function Markdown({ children }: { children: string }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={{ pre: CodeBlock }}>{children}</ReactMarkdown></div>;
}

function CodeBlock({ children, ...props }: ComponentPropsWithoutRef<"pre">) {
  const ref = useRef<HTMLPreElement>(null);
  return <div className="code-block"><button type="button" className="code-copy" aria-label="Copy code" onClick={() => void copyText(ref.current?.textContent ?? "")}>Copy</button><pre {...props} ref={ref}>{children}</pre></div>;
}

function Skeleton() {
  return <div className="skeleton" data-testid="skeleton" aria-hidden="true">{Array.from({ length: 3 }, (_, index) => <div key={index} className="skeleton-row" />)}</div>;
}

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the browser-supported legacy path.
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(area);
    return copied;
  } catch {
    return false;
  }
}
