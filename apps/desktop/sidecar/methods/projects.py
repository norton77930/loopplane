"""Profile-owned project RPC methods (078 T042)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..profile import ProfileState
    from ..projects import ProjectStore
    from ..protocol import RpcError
except ImportError:  # pragma: no cover
    from profile import ProfileState  # type: ignore[no-redef]

    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
    from projects import ProjectStore  # type: ignore[no-redef]
    from protocol import RpcError  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]

_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=False,
    message_key="desktop.error.busy",
)
_NOT_FOUND = RpcError(
    code=-32005,
    message="Not found",
    category="not_found",
    retryable=False,
    message_key="desktop.error.not_found",
)
_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="protocol",
    retryable=False,
    message_key="desktop.error.invalid_params",
)


class ProjectMethods:
    def __init__(
        self,
        state: ProfileState,
        lease: ProfileMutationLease,
    ) -> None:
        self._store = ProjectStore(state)
        self._lease = lease

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "project.list": self.list_projects,
            "project.create": self.create,
            "project.rename": self.rename,
            "project.remove": self.remove,
            "project.assignSession": self.assign_session,
        }

    async def list_projects(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"projects": self._store.list()}

    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        label = params.get("label")
        if not isinstance(label, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("project", mutation_id)
            self._lease.acquire("project", mutation_id)
            try:
                project = self._store.create(
                    label=label,
                    workspace_id=params.get("workspace_id")
                    if isinstance(params.get("workspace_id"), str)
                    else None,
                )
            finally:
                self._lease.release("project", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except ValueError as exc:
            raise _INVALID from exc
        return {"project": project}

    async def rename(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        project_id = params.get("project_id")
        label = params.get("label")
        if not isinstance(project_id, str) or not isinstance(label, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("project", mutation_id)
            self._lease.acquire("project", mutation_id)
            try:
                project = self._store.rename(project_id, label)
            finally:
                self._lease.release("project", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        except ValueError as exc:
            raise _INVALID from exc
        return {"project": project}

    async def remove(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        project_id = params.get("project_id")
        if not isinstance(project_id, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("project", mutation_id)
            self._lease.acquire("project", mutation_id)
            try:
                self._store.remove(project_id)
            finally:
                self._lease.release("project", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        return {"removed": True, "project_id": project_id}

    async def assign_session(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        session_id = params.get("session_id")
        if not isinstance(session_id, str):
            raise _INVALID
        project_id = params.get("project_id")
        if project_id is not None and not isinstance(project_id, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("project", mutation_id)
            self._lease.acquire("project", mutation_id)
            try:
                project = self._store.assign_session(project_id, session_id)
            finally:
                self._lease.release("project", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        return {"project": project, "session_id": session_id}


def _require_mutation(params: dict[str, Any]) -> str:
    mid = params.get("mutation_id")
    if not isinstance(mid, str) or not mid.strip():
        raise _INVALID
    return mid
