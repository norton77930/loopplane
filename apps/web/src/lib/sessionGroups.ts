// Group sessions by recency for the sidebar (unit 030): Today / Yesterday / Earlier,
// bucketed by the viewer's local day from `last_active_at`. A pure helper — `now` is
// injectable for tests. Input order is preserved within a bucket (the server lists
// newest-first), and empty buckets are omitted.

import type { SessionSummary } from "../api/types";

export type GroupKey = "today" | "yesterday" | "earlier";

export interface SessionGroup {
  key: GroupKey;
  sessions: SessionSummary[];
}

const DAY_MS = 86_400_000;

function localDayDiff(now: Date, then: Date): number {
  const a = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const b = new Date(then.getFullYear(), then.getMonth(), then.getDate()).getTime();
  return Math.round((a - b) / DAY_MS);
}

export function groupSessions(
  sessions: SessionSummary[],
  now: Date = new Date(),
): SessionGroup[] {
  const buckets: Record<GroupKey, SessionSummary[]> = {
    today: [],
    yesterday: [],
    earlier: [],
  };
  for (const session of sessions) {
    const when = new Date(session.last_active_at);
    const diff = Number.isNaN(when.getTime()) ? Infinity : localDayDiff(now, when);
    const key: GroupKey = diff <= 0 ? "today" : diff === 1 ? "yesterday" : "earlier";
    buckets[key].push(session);
  }
  return (["today", "yesterday", "earlier"] as GroupKey[])
    .filter((key) => buckets[key].length > 0)
    .map((key) => ({ key, sessions: buckets[key] }));
}
