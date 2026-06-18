import type { SessionSummary } from "../api/types";

// The sessions sidebar (FR-008): lists existing sessions with recency and a new-chat action;
// an empty list shows a clear empty state.
interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
}

export function Sidebar({ sessions, activeId, onOpen, onNew }: Props) {
  return (
    <>
      <div className="sidebar-title">LoopPlane</div>
      <button type="button" className="new-chat" onClick={onNew}>
        + New chat
      </button>
      {sessions.length === 0 ? (
        <div className="sidebar-empty">No sessions yet.</div>
      ) : (
        <ul className="session-list" data-testid="sessions">
          {sessions.map((session) => (
            <li key={session.session_id} className="session-item">
              <button
                type="button"
                aria-current={session.session_id === activeId}
                onClick={() => onOpen(session.session_id)}
              >
                {session.session_id}
              </button>
              <span className="recency">{session.last_active_at}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
