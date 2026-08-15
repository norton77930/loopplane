/**
 * Persisted session / project / workspace navigation (078 T045).
 *
 * Sessions are the surface a person opens the application to use; projects are a
 * way to group them and a workspace is chosen once and then lived with. The
 * three used to be sibling sections with identical weight, which made the list
 * you touch every day the same size as the one you set up once. Sessions now
 * take the column, projects collapse below them, and the bound workspace sits in
 * a persistent footer with the settings it belongs next to.
 *
 * Renderer-only draft note: unsent composer text is never listed here.
 */

import { initTheme, toggleTheme, type Theme } from "@loopplane/cowork-presentation";
import { useMemo, useState } from "react";

import { DESKTOP_LOCALES, useTranslation } from "../i18n";

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
  /** Footer actions; omitted hosts simply get no button. */
  onOpenSettings?: () => void;
  onOpenBackup?: () => void;
};

const AVAILABILITY_KEY: Record<string, string> = {
  available: "workspace.ready",
  relink_required: "workspace.moved",
  missing: "workspace.missing",
};

function sessionTitle(session: SessionSummaryView): string {
  return session.title?.trim() || session.session_id.slice(0, 8);
}

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
  onOpenSettings,
  onOpenBackup,
}: SessionSidebarProps) {
  const { t, locale, setLocale } = useTranslation();
  const availabilityLabel = (availability: string): string => {
    const key = AVAILABILITY_KEY[availability];
    // An unrecognized availability shows its own value rather than a guess.
    return key ? t(key) : availability;
  };
  const [query, setQuery] = useState("");
  // Resolved once from the stored choice, falling back to the OS preference.
  const [theme, setTheme] = useState<Theme>(() => initTheme());

  // Grouping is starred-first rather than by recency: `session.list` projects
  // only id, title, starred and principal, so the renderer has no timestamp to
  // bucket by and inventing one would mean changing the sidecar payload.
  const { starred, rest } = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = needle
      ? sessions.filter((session) =>
          sessionTitle(session).toLowerCase().includes(needle),
        )
      : sessions;
    return {
      starred: matching.filter((session) => session.starred),
      rest: matching.filter((session) => !session.starred),
    };
  }, [sessions, query]);

  const selectedWorkspace =
    workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null;

  function renderSession(session: SessionSummaryView) {
    const title = sessionTitle(session);
    const isStarred = Boolean(session.starred);
    const active = activeSessionId === session.session_id;
    return (
      <li key={session.session_id} className="session-row">
        <button
          type="button"
          className={active ? "selected" : undefined}
          aria-current={active ? "true" : undefined}
          disabled={busy}
          onClick={() => onSelectSession(session.session_id)}
        >
          {title}
        </button>
        {/* Row actions stay in the accessibility tree and reachable by keyboard;
            CSS only fades them until the row is hovered or focused, so three
            buttons per row stop competing with the titles. */}
        <span className="session-row-actions">
          <button
            type="button"
            aria-label={isStarred ? t("sidebar.unstar") : t("sidebar.star")}
            disabled={busy}
            onClick={() => onToggleStar(session.session_id, !isStarred)}
          >
            {isStarred ? "★" : "☆"}
          </button>
          <button
            type="button"
            aria-label={t("sidebar.fork")}
            disabled={busy}
            onClick={() => onForkSession(session.session_id)}
          >
            {t("sidebar.fork")}
          </button>
          <button
            type="button"
            aria-label={t("sidebar.delete")}
            disabled={busy}
            onClick={() => onDeleteSession(session.session_id)}
          >
            {t("sidebar.delete")}
          </button>
        </span>
      </li>
    );
  }

  return (
    <aside className="session-sidebar" aria-label="Sessions and workspaces">
      <div className="sidebar-top">
        <button
          type="button"
          className="primary sidebar-new-session"
          aria-label="LoopPlane smoke new session"
          disabled={busy}
          onClick={() => onNewSession()}
        >
          {t("sidebar.newSession")}
        </button>
        <input
          type="search"
          className="sidebar-search"
          aria-label={t("sidebar.searchLabel")}
          placeholder={t("sidebar.search")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {/* One list, so the fixed packaged-smoke locator resolves to exactly one
          element: the group headings are rows inside it, not separate lists. */}
      <ul aria-label="LoopPlane smoke session list" data-testid="session-list">
        {starred.length > 0 && (
          <li className="session-group-heading" role="presentation">
            {t("sidebar.starred")}
          </li>
        )}
        {starred.map(renderSession)}
        {starred.length > 0 && rest.length > 0 && (
          <li className="session-group-heading" role="presentation">
            {t("sidebar.allSessions")}
          </li>
        )}
        {rest.map(renderSession)}
        {starred.length === 0 && rest.length === 0 && (
          <li className="empty">
            {query.trim() ? t("sidebar.noMatches") : t("sidebar.noSessions")}
          </li>
        )}
      </ul>

      <details className="sidebar-projects">
        <summary>
          {t("sidebar.projects")}<span className="sidebar-count">{projects.length}</span>
        </summary>
        <div className="sidebar-section-header">
          <button type="button" disabled={busy} onClick={() => onCreateProject()}>
            {t("sidebar.newProject")}
          </button>
        </div>
        <ul data-testid="project-list">
          {projects.map((project) => (
            <li key={project.id}>
              <span>{project.label}</span>
              <button
                type="button"
                aria-label={t("sidebar.removeProjectLabel", { name: project.label })}
                disabled={busy}
                onClick={() => onRemoveProject(project.id)}
              >
                {t("sidebar.removeProject")}
              </button>
            </li>
          ))}
          {projects.length === 0 && <li className="empty">{t("sidebar.noProjects")}</li>}
        </ul>
        <p className="hint">
          {t("sidebar.projectHint")}
        </p>
      </details>

      <div className="sidebar-footer">
        <details className="sidebar-workspaces">
          <summary>
            <span className="workspace-current">
              {selectedWorkspace ? `⌂ ${selectedWorkspace.label}` : t("sidebar.noFolder")}
            </span>
            {selectedWorkspace && (
              <span className="availability">
                {availabilityLabel(selectedWorkspace.availability)}
              </span>
            )}
          </summary>
          <ul data-testid="workspace-list">
            {workspaces.map((workspace) => (
              <li key={workspace.id}>
                <button
                  type="button"
                  className={
                    selectedWorkspaceId === workspace.id ? "selected" : undefined
                  }
                  aria-current={
                    selectedWorkspaceId === workspace.id ? "true" : undefined
                  }
                  disabled={busy}
                  onClick={() => onSelectWorkspace(workspace.id)}
                >
                  {workspace.label}
                  <span className="availability">
                    {" "}
                    ({availabilityLabel(workspace.availability)})
                  </span>
                </button>
                {workspace.availability === "relink_required" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onRelinkWorkspace(workspace.id)}
                  >
                    {t("sidebar.relink")}
                  </button>
                )}
              </li>
            ))}
            {workspaces.length === 0 && (
              <li className="empty">{t("sidebar.noWorkspaces")}</li>
            )}
          </ul>
          <div className="sidebar-section-header">
            <button type="button" disabled={busy} onClick={() => onBindWorkspace()}>
              {t("sidebar.bindFolder")}
            </button>
          </div>
        </details>

        <div className="sidebar-footer-actions">
          {onOpenSettings && (
            <button type="button" onClick={onOpenSettings}>
              {t("sidebar.settings")}
            </button>
          )}
          {onOpenBackup && (
            <button type="button" onClick={onOpenBackup}>
              {t("sidebar.backup")}
            </button>
          )}
        </div>
        {/* A second row: four controls do not fit the sidebar's width, and a
            single item wrapping alone reads as a mistake rather than a group. */}
        <div className="sidebar-footer-prefs">
          <select
            className="sidebar-language"
            aria-label={t("sidebar.language")}
            value={locale}
            onChange={(event) =>
              setLocale(event.target.value as (typeof DESKTOP_LOCALES)[number]["id"])
            }
          >
            {DESKTOP_LOCALES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="sidebar-theme-toggle"
            aria-label={
              theme === "dark" ? t("sidebar.toLight") : t("sidebar.toDark")
            }
            title={theme === "dark" ? t("sidebar.toLight") : t("sidebar.toDark")}
            onClick={() => setTheme((current) => toggleTheme(current))}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </div>
    </aside>
  );
}
