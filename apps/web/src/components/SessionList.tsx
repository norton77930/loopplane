import type { SessionSummary } from "../api/types";

interface Props {
  sessions: SessionSummary[];
  onOpen: (id: string) => void;
}

export function SessionList({ sessions, onOpen }: Props) {
  if (sessions.length === 0) {
    return (
      <div className="sessions sessions-empty" data-testid="sessions">
        No sessions yet.
      </div>
    );
  }
  return (
    <ul className="sessions" data-testid="sessions">
      {sessions.map((session) => (
        <li key={session.session_id} className="session">
          <button type="button" onClick={() => onOpen(session.session_id)}>
            {session.session_id}
          </button>
          <span className="recency">{session.last_active_at}</span>
        </li>
      ))}
    </ul>
  );
}
