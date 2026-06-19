import type { SessionSummary } from "../api/types";
import { groupSessions } from "../lib/sessionGroups";

const at = (iso: string): SessionSummary => ({
  session_id: iso,
  label: null,
  last_active_at: iso,
  created_at: iso,
});

const NOW = new Date("2026-06-19T12:00:00");

describe("groupSessions", () => {
  it("buckets sessions into today / yesterday / earlier by local day", () => {
    const groups = groupSessions(
      [
        at("2026-06-19T09:00:00"), // today
        at("2026-06-18T23:00:00"), // yesterday
        at("2026-06-10T10:00:00"), // earlier
      ],
      NOW,
    );
    expect(groups.map((g) => g.key)).toEqual(["today", "yesterday", "earlier"]);
    expect(groups[0].sessions).toHaveLength(1);
  });

  it("omits empty buckets and preserves input order within a bucket", () => {
    const groups = groupSessions(
      [at("2026-06-19T09:00:00"), at("2026-06-19T08:00:00")],
      NOW,
    );
    expect(groups.map((g) => g.key)).toEqual(["today"]);
    expect(groups[0].sessions.map((s) => s.session_id)).toEqual([
      "2026-06-19T09:00:00",
      "2026-06-19T08:00:00",
    ]);
  });

  it("treats an unparseable timestamp as earlier (graceful)", () => {
    const groups = groupSessions([at("not-a-date")], NOW);
    expect(groups.map((g) => g.key)).toEqual(["earlier"]);
  });
});
