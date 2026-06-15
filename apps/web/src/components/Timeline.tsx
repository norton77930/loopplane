import type { TimelineEntry } from "../state/chat";

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <ul className="timeline" data-testid="timeline">
      {entries.map((entry, index) =>
        entry.kind === "tool" ? (
          <li key={index} className="timeline-tool">
            tool {entry.name} — {entry.outcome ?? "running"}
          </li>
        ) : (
          <li key={index} className="timeline-terminated">
            run {entry.reason} ({entry.turns} turn{entry.turns === 1 ? "" : "s"})
          </li>
        ),
      )}
    </ul>
  );
}
