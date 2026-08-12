"""Profile-owned Desktop Projects (078 T039).

Grouping metadata only — never deletes sessions, workspaces, or filesystem data.
"""

from __future__ import annotations

import uuid
from typing import Any

try:
    from .profile import ProfileState
except ImportError:  # pragma: no cover
    from profile import ProfileState  # type: ignore[no-redef]


class ProjectStore:
    def __init__(self, state: ProfileState) -> None:
        self._state = state

    def list(self) -> list[dict[str, Any]]:
        data = self._state.load_portable()
        projects = data.get("projects")
        if not isinstance(projects, list):
            return []
        return [dict(p) for p in projects if isinstance(p, dict)]

    def create(self, *, label: str, workspace_id: str | None = None) -> dict[str, Any]:
        label = _bounded_label(label)
        data = self._state.load_portable()
        projects: list[dict[str, Any]] = list(data.get("projects") or [])
        project = {
            "id": str(uuid.uuid4()),
            "label": label,
            "workspace_id": workspace_id,
            "session_ids": [],
        }
        projects.append(project)
        data["projects"] = projects
        self._state.save_portable(data)
        return dict(project)

    def rename(self, project_id: str, label: str) -> dict[str, Any]:
        label = _bounded_label(label)
        data = self._state.load_portable()
        projects: list[dict[str, Any]] = list(data.get("projects") or [])
        for p in projects:
            if p.get("id") == project_id:
                p["label"] = label
                self._state.save_portable({**data, "projects": projects})
                return dict(p)
        raise KeyError("project not found")

    def remove(self, project_id: str) -> None:
        data = self._state.load_portable()
        projects: list[dict[str, Any]] = list(data.get("projects") or [])
        new_projects = [p for p in projects if p.get("id") != project_id]
        if len(new_projects) == len(projects):
            raise KeyError("project not found")
        data["projects"] = new_projects
        self._state.save_portable(data)

    def assign_session(
        self, project_id: str | None, session_id: str
    ) -> dict[str, Any] | None:
        """Assign session to at most one project; None unassigns."""

        data = self._state.load_portable()
        projects: list[dict[str, Any]] = list(data.get("projects") or [])
        for p in projects:
            ids = list(p.get("session_ids") or [])
            if session_id in ids:
                ids = [s for s in ids if s != session_id]
                p["session_ids"] = ids
        result: dict[str, Any] | None = None
        if project_id is not None:
            found = False
            for p in projects:
                if p.get("id") == project_id:
                    ids = list(p.get("session_ids") or [])
                    if session_id not in ids:
                        ids.append(session_id)
                    p["session_ids"] = ids
                    result = dict(p)
                    found = True
                    break
            if not found:
                raise KeyError("project not found")
        data["projects"] = projects
        self._state.save_portable(data)
        return result

    def session_project(self, session_id: str) -> str | None:
        for p in self.list():
            if session_id in (p.get("session_ids") or []):
                return str(p.get("id"))
        return None


def _bounded_label(label: str) -> str:
    text = label.strip()
    if not text:
        raise ValueError("empty label")
    if len(text.encode("utf-8")) > 4096:
        raise ValueError("label too large")
    return text
