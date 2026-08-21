export type AuditEntry = {
  audit_id: string;
  session_id: string;
  turn_ordinal: number;
  checkpoint_sequence: number;
  recorded_at: string | null;
  state: "completed" | "interrupted";
  termination_reason: string | null;
  turns_taken: number | null;
};

export type AuditViewProps = {
  entries: AuditEntry[];
  loading?: boolean;
  failed?: boolean;
};

export function AuditView({ entries, loading = false, failed = false }: AuditViewProps) {
  if (loading) {
    return <div role="status">Loading turn audit…</div>;
  }

  if (failed) {
    return <div role="alert">Turn audit unavailable.</div>;
  }

  return (
    <section aria-label="Turn audit">
      {entries.length === 0 ? (
        <p>No audit entries.</p>
      ) : (
        <ul>
          {entries.map((entry) => (
            <li key={entry.audit_id}>
              <span>{entry.state}</span>
              {entry.termination_reason && (
                <span> · {entry.termination_reason}</span>
              )}
              {entry.turns_taken !== null && (
                <span>
                  {" "}· {entry.turns_taken} {entry.turns_taken === 1 ? "turn" : "turns"}
                </span>
              )}
              <span>
                {" "}· Turn {entry.turn_ordinal} · Checkpoint {entry.checkpoint_sequence}
              </span>
              {entry.recorded_at && <time dateTime={entry.recorded_at}> · {entry.recorded_at}</time>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
