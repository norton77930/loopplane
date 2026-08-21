"""Device-private Workspace Bindings + safe Reference projections (078 T040)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from .mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from .profile import ProfileState
except ImportError:  # pragma: no cover
    from profile import ProfileState  # type: ignore[no-redef]

    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )


class WorkspaceStore:
    def __init__(self, state: ProfileState) -> None:
        self._state = state
        self._bindings_path = state.root / "device-private" / "workspace-bindings.json"

    def list(self) -> list[dict[str, Any]]:
        data = self._state.load_portable()
        refs = data.get("workspace_references")
        if not isinstance(refs, list):
            return []
        return [_safe_ref(r) for r in refs if isinstance(r, dict)]

    def bind(self, path: Path, *, label: str = "Workspace") -> dict[str, Any]:
        resolved = _validate_directory(path)
        workspace_id = str(uuid.uuid4())
        ref = {
            "id": workspace_id,
            "label": label.strip() or "Workspace",
            "availability": "available",
            "actions": ["open", "relink", "remove"],
        }
        data = self._state.load_portable()
        refs = list(data.get("workspace_references") or [])
        refs.append(ref)
        data["workspace_references"] = refs
        self._state.save_portable(data)
        bindings = self._load_bindings()
        bindings[workspace_id] = {
            "canonical_path": str(resolved),
            "validated_at": time.time(),
            "profile_id": self._state.profile_id,
        }
        self._save_bindings(bindings)
        return _safe_ref(ref)

    def relink(self, workspace_id: str, path: Path) -> dict[str, Any]:
        resolved = _validate_directory(path)
        data = self._state.load_portable()
        refs = list(data.get("workspace_references") or [])
        found = None
        for r in refs:
            if r.get("id") == workspace_id:
                r["availability"] = "available"
                found = r
                break
        if found is None:
            raise KeyError("workspace not found")
        data["workspace_references"] = refs
        self._state.save_portable(data)
        bindings = self._load_bindings()
        bindings[workspace_id] = {
            "canonical_path": str(resolved),
            "validated_at": time.time(),
            "profile_id": self._state.profile_id,
        }
        self._save_bindings(bindings)
        return _safe_ref(found)

    def remove(self, workspace_id: str) -> None:
        data = self._state.load_portable()
        refs = [
            r
            for r in (data.get("workspace_references") or [])
            if r.get("id") != workspace_id
        ]
        data["workspace_references"] = refs
        self._state.save_portable(data)
        bindings = self._load_bindings()
        bindings.pop(workspace_id, None)
        self._save_bindings(bindings)

    def mark_relink_required(self, workspace_id: str) -> None:
        data = self._state.load_portable()
        refs = list(data.get("workspace_references") or [])
        for r in refs:
            if r.get("id") == workspace_id:
                r["availability"] = "relink_required"
        data["workspace_references"] = refs
        self._state.save_portable(data)

    def resolve_path(self, workspace_id: str) -> Path:
        """Resolve binding only when reference is not relink_required."""

        ref = self._ref(workspace_id)
        if ref.get("availability") == "relink_required":
            err = LookupError("workspace relink required")
            err.public_code = "workspace_relink_required"  # type: ignore[attr-defined]
            raise err
        bindings = self._load_bindings()
        entry = bindings.get(workspace_id)
        if not entry:
            raise LookupError("workspace binding missing")
        # Stale identical-ID after restore: profile_id mismatch ignores binding.
        if entry.get("profile_id") not in (None, self._state.profile_id):
            raise LookupError("stale workspace binding")
        path = Path(str(entry["canonical_path"]))
        if not path.is_dir():
            raise LookupError("workspace path unavailable")
        return path.resolve()

    def revalidate(
        self,
        workspace_id: str,
        *,
        lease: ProfileMutationLease | None = None,
        lease_owner: str = "workspace.revalidate",
        mutation_identity: str | None = None,
    ) -> dict[str, Any]:
        if lease is not None:
            try:
                lease.require_free_or_owner(lease_owner, mutation_identity)
                lease.acquire(lease_owner, mutation_identity)
            except MutationLeaseBusy:
                raise
            except RuntimeError:
                raise
        try:
            # Hard denial when relink_required — ignore stale binding.
            ref = self._ref(workspace_id)
            if ref.get("availability") == "relink_required":
                err = LookupError("workspace relink required")
                err.public_code = "workspace_relink_required"  # type: ignore[attr-defined]
                raise err
            path = self.resolve_path(workspace_id)
            _validate_directory(path)
            bindings = self._load_bindings()
            entry = bindings.get(workspace_id) or {}
            entry["validated_at"] = time.time()
            entry["canonical_path"] = str(path.resolve())
            entry["profile_id"] = self._state.profile_id
            bindings[workspace_id] = entry
            self._save_bindings(bindings)
            data = self._state.load_portable()
            refs = list(data.get("workspace_references") or [])
            for r in refs:
                if r.get("id") == workspace_id:
                    r["availability"] = "available"
            data["workspace_references"] = refs
            self._state.save_portable(data)
            return self._ref(workspace_id)
        finally:
            if lease is not None and lease.held_by(
                lease_owner, mutation_identity or lease_owner
            ):
                lease.release(lease_owner, mutation_identity)

    def _ref(self, workspace_id: str) -> dict[str, Any]:
        for r in self.list():
            if r.get("id") == workspace_id:
                return r
        # list returns safe copies; re-read portable for full.
        data = self._state.load_portable()
        for r in data.get("workspace_references") or []:
            if isinstance(r, dict) and r.get("id") == workspace_id:
                return _safe_ref(r)
        raise KeyError("workspace not found")

    def _load_bindings(self) -> dict[str, Any]:
        path = self._bindings_path
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _save_bindings(self, bindings: dict[str, Any]) -> None:
        path = self._bindings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(bindings, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)


def _safe_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(ref.get("id", "")),
        "label": str(ref.get("label", "Workspace")),
        "availability": str(ref.get("availability", "unavailable")),
        "actions": list(ref.get("actions") or ["open", "relink", "remove"]),
    }


def _validate_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("not a directory")
    return resolved
