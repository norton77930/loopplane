/**
 * Persisted session / project / workspace navigation (078 T045).
 *
 * Renderer-only draft note: unsent composer text is never listed here.
 */

import type {
  ProjectView,
  SessionSummaryView,
  WorkspaceView,
} from "../sidecar";

export type SessionSidebarProps = {
  sessions: SessionSummaryView[];
  projects: ProjectView[];
  workspaces: WorkspaceView[];
  activeSessionId?: string | null;
  selectedWorkspaceId?: string | null;
  busy?: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onToggleStar: (sessionId: string, starred: boolean) => void;
  onDeleteSession: (sessionId: string) => void;
  onForkSession: (sessionId: string) => void;
  onCreateProject: () => void;
  onRemoveProject: (projectId: string) => void;
  onBindWorkspace: () => void;
  onRelinkWorkspace: (workspaceId: string) => void;
  onSelectWorkspace: (workspaceId: string | null) => void;
};

export function SessionSidebar({
  sessions,
  projects,
  workspaces,
  activeSessionId,
  selectedWorkspaceId,
  busy = false,
  onSelectSession,
  onNewSession,
  onToggleStar,
  onDeleteSession,
  onForkSession,
  onCreateProject,
  onRemoveProject,
  onBindWorkspace,
  onRelinkWorkspace,
  onSelectWorkspace,
}: SessionSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="Sessions and workspaces">
      <section aria-label="Workspaces">
        <header className="sidebar-section-header">
          <h2>Workspaces</h2>
          <button
            type="button"
            disabled={busy}
            onClick={() => onBindWorkspace()}
          >
            Bind…
          </button>
        </header>
        <ul data-testid="workspace-list">
          {workspaces.map((ws) => (
            <li key={ws.id}>
              <button
                type="button"
                className={
                  selectedWorkspaceId === ws.id ? "selected" : undefined
                }
                aria-current={selectedWorkspaceId === ws.id ? "true" : undefined}
                disabled={busy}
                onClick={() => onSelectWorkspace(ws.id)}
              >
                {ws.label}
                <span className="availability"> ({ws.availability})</span>
              </button>
              {ws.availability === "relink_required" && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onRelinkWorkspace(ws.id)}
                >
                  Relink…
                </button>
              )}
            </li>
          ))}
          {workspaces.length === 0 && (
            <li className="empty">No workspaces bound</li>
          )}
        </ul>
      </section>

      <section aria-label="Projects">
        <header className="sidebar-section-header">
          <h2>Projects</h2>
          <button
            type="button"
            disabled={busy}
            onClick={() => onCreateProject()}
          >
            New
          </button>
        </header>
        <ul data-testid="project-list">
          {projects.map((p) => (
            <li key={p.id}>
              <span>{p.label}</span>
              <button
                type="button"
                aria-label={`Remove project ${p.label}`}
                disabled={busy}
                onClick={() => onRemoveProject(p.id)}
              >
                Remove
              </button>
            </li>
          ))}
          {projects.length === 0 && (
            <li className="empty">No projects</li>
          )}
        </ul>
        <p className="hint">
          Removing a project ungroups sessions; it does not delete them.
        </p>
      </section>

      <section aria-label="Sessions">
        <header className="sidebar-section-header">
          <h2>Sessions</h2>
          <button
            type="button"
            aria-label="LoopPlane smoke new session"
            disabled={busy}
            onClick={() => onNewSession()}
          >
            New
          </button>
        </header>
        <ul
          aria-label="LoopPlane smoke session list"
          data-testid="session-list"
        >
          {sessions.map((s) => {
            const title = s.title?.trim() || s.session_id.slice(0, 8);
            const starred = Boolean(s.starred);
            return (
              <li key={s.session_id}>
                <button
                  type="button"
                  className={
                    activeSessionId === s.session_id ? "selected" : undefined
                  }
                  aria-current={
                    activeSessionId === s.session_id ? "true" : undefined
                  }
                  disabled={busy}
                  onClick={() => onSelectSession(s.session_id)}
                >
                  {starred ? "★ " : ""}
                  {title}
                </button>
                <button
                  type="button"
                  aria-label={starred ? "Unstar session" : "Star session"}
                  disabled={busy}
                  onClick={() => onToggleStar(s.session_id, !starred)}
                >
                  {starred ? "Unstar" : "Star"}
                </button>
                <button
                  type="button"
                  aria-label="Fork session"
                  disabled={busy}
                  onClick={() => onForkSession(s.session_id)}
                >
                  Fork
                </button>
                <button
                  type="button"
                  aria-label="Delete session"
                  disabled={busy}
                  onClick={() => onDeleteSession(s.session_id)}
                >
                  Delete
                </button>
              </li>
            );
          })}
          {sessions.length === 0 && (
            <li className="empty">No sessions yet</li>
          )}
        </ul>
      </section>
    </aside>
  );
}
