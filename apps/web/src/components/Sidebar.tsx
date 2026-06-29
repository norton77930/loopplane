import { useState } from "react";

import type { SessionSummary } from "../api/types";
import { useTranslation } from "../i18n/i18n";
import { groupSessions, type GroupKey } from "../lib/sessionGroups";
import { Skeleton } from "./Skeleton";

// The sessions sidebar (FR-008; 030): lists sessions by a human title (label, with a short-id
// fallback), grouped Today / Yesterday / Earlier, each with a rename + delete affordance.
interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  onToggleStar?: (id: string, next: boolean) => void;
  onSearch?: (query: string) => void;
  onBulkDelete?: (ids: string[]) => void;
  loading?: boolean;
}

const GROUP_LABEL: Record<GroupKey, string> = {
  today: "sidebar.today",
  yesterday: "sidebar.yesterday",
  earlier: "sidebar.earlier",
};

export function Sidebar({
  sessions,
  activeId,
  onOpen,
  onNew,
  onRename,
  onDelete,
  onToggleStar,
  onSearch,
  onBulkDelete,
  loading,
}: Props) {
  const { t } = useTranslation();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const groups = groupSessions(sessions);

  function toggleSelected(id: string, selected: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function bulkDelete() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (window.confirm(t("sidebar.deleteConfirm"))) {
      onBulkDelete?.(ids);
      setSelectedIds(new Set());
    }
  }
  return (
    <>
      <div className="sidebar-title">LoopPlane</div>
      <button type="button" className="new-chat" onClick={onNew}>
        {t("sidebar.newChat")}
      </button>
      {onSearch && (
        <input
          className="session-search"
          aria-label="search sessions"
          type="search"
          onChange={(event) => onSearch(event.target.value)}
        />
      )}
      {onBulkDelete && selectedIds.size > 0 && (
        <button type="button" className="bulk-delete" onClick={bulkDelete}>
          Delete selected
        </button>
      )}
      {loading && sessions.length === 0 ? (
        <Skeleton rows={4} />
      ) : sessions.length === 0 ? (
        <div className="sidebar-empty">{t("sidebar.empty")}</div>
      ) : (
        <div className="session-list" data-testid="sessions">
          {groups.map((group) => (
            <div key={group.key} className="session-group">
              <div className="session-group-title">{t(GROUP_LABEL[group.key])}</div>
              <ul>
                {group.sessions.map((session) => (
                  <SessionRow
                    key={session.session_id}
                    session={session}
                    active={session.session_id === activeId}
                    onOpen={onOpen}
                    onRename={onRename}
                    onDelete={onDelete}
                    onToggleStar={onToggleStar}
                    selectable={Boolean(onBulkDelete)}
                    selected={selectedIds.has(session.session_id)}
                    onSelect={toggleSelected}
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

interface RowProps {
  session: SessionSummary;
  active: boolean;
  onOpen: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
  onToggleStar?: (id: string, next: boolean) => void;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: string, selected: boolean) => void;
}

function SessionRow({
  session,
  active,
  onOpen,
  onRename,
  onDelete,
  onToggleStar,
  selectable,
  selected,
  onSelect,
}: RowProps) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState("");
  const title = session.label ?? session.session_id.slice(0, 8);

  // Enter saves; Escape or blur (click away) cancels.
  function save() {
    const value = draft.trim();
    if (value) onRename?.(session.session_id, value);
    setRenaming(false);
  }

  if (renaming) {
    return (
      <li className="session-item">
        <input
          className="session-rename"
          aria-label="rename session"
          autoFocus
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") save();
            else if (event.key === "Escape") setRenaming(false);
          }}
          onBlur={() => setRenaming(false)}
        />
      </li>
    );
  }

  return (
    <li className="session-item">
      {selectable && (
        <input
          type="checkbox"
          aria-label={`select ${title}`}
          checked={Boolean(selected)}
          onChange={(event) => onSelect?.(session.session_id, event.target.checked)}
        />
      )}
      {onToggleStar && (
        <button
          type="button"
          className="session-star"
          aria-label={`${session.starred ? "unstar" : "star"} session ${title}`}
          onClick={() => onToggleStar(session.session_id, !session.starred)}
        >
          {session.starred ? "★" : "☆"}
        </button>
      )}
      <button
        type="button"
        className="session-open"
        aria-current={active}
        onClick={() => onOpen(session.session_id)}
      >
        {title}
      </button>
      {(onRename || onDelete) && (
        <div className="session-menu">
          <button
            type="button"
            aria-label="session menu"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ⋯
          </button>
          {menuOpen && (
            <ul className="menu-popup" role="menu">
              {onRename && (
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      setDraft(session.label ?? "");
                      setRenaming(true);
                      setMenuOpen(false);
                    }}
                  >
                    {t("sidebar.rename")}
                  </button>
                </li>
              )}
              {onDelete && (
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      if (window.confirm(t("sidebar.deleteConfirm"))) {
                        onDelete(session.session_id);
                      }
                    }}
                  >
                    {t("sidebar.delete")}
                  </button>
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}
