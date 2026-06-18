import { useEffect, useRef, useState } from "react";

import type { ConversationEntry } from "../state/chat";
import { Markdown } from "./Markdown";
import { ToolCard } from "./ToolCard";

const BOTTOM_THRESHOLD = 40;

// The scrolling message region: renders the ordered entries (FR-001/002/006) and owns its
// own scroll container so it can auto-scroll when pinned to the bottom and offer a
// jump-to-latest affordance when the user has scrolled up (FR-011).
export function MessageList({ entries }: { entries: ConversationEntry[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

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
        <Entry key={index} entry={entry} />
      ))}
      {!pinned && (
        <button type="button" className="jump-latest" onClick={jumpToLatest}>
          Jump to latest
        </button>
      )}
    </div>
  );
}

function Entry({ entry }: { entry: ConversationEntry }) {
  switch (entry.kind) {
    case "user":
      return (
        <div className="message message-user">
          <div className="message-role">You</div>
          <div className="bubble">{entry.text}</div>
        </div>
      );
    case "assistant":
      return (
        <div className="message message-assistant">
          <div className="message-role">LoopPlane</div>
          <Markdown>{entry.text}</Markdown>
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
