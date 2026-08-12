"""Workspace bind/list/relink/remove/revalidate RPC (078 T041).

Absolute paths are trusted main-to-sidecar only and never returned.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..profile import ProfileState
    from ..protocol import RpcError
    from ..workspace import WorkspaceStore
except ImportError:  # pragma: no cover
    from profile import ProfileState  # type: ignore[no-redef]

    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
    from protocol import RpcError  # type: ignore[no-redef]
    from workspace import WorkspaceStore  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]

_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=False,
    message_key="desktop.error.busy",
)
_NOT_FOUND = RpcError(
    code=-32002,
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
_RELINK = RpcError(
    code=-32006,
    message="Workspace relink required",
    category="workspace_relink_required",
    retryable=False,
    message_key="desktop.error.workspace_relink_required",
    recovery="relink_workspace",
)


class WorkspaceMethods:
    def __init__(
        self,
        state: ProfileState,
        lease: ProfileMutationLease,
    ) -> None:
        self._store = WorkspaceStore(state)
        self._lease = lease

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "workspace.list": self.list_workspaces,
            "workspace.bind": self.bind,
            "workspace.relink": self.relink,
            "workspace.remove": self.remove,
            "workspace.revalidate": self.revalidate,
        }

    async def list_workspaces(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"workspaces": self._store.list()}

    async def bind(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        path = params.get("path")
        if not isinstance(path, str) or not path.strip():
            raise _INVALID
        label = (
            params.get("label") if isinstance(params.get("label"), str) else "Workspace"
        )
        try:
            self._lease.require_free_or_owner("workspace", mutation_id)
            self._lease.acquire("workspace", mutation_id)
            try:
                ref = self._store.bind(Path(path), label=label)
            finally:
                self._lease.release("workspace", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except ValueError as exc:
            raise _INVALID from exc
        return {"workspace": ref}

    async def relink(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        workspace_id = params.get("workspace_id")
        path = params.get("path")
        if not isinstance(workspace_id, str) or not isinstance(path, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("workspace", mutation_id)
            self._lease.acquire("workspace", mutation_id)
            try:
                ref = self._store.relink(workspace_id, Path(path))
            finally:
                self._lease.release("workspace", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        except ValueError as exc:
            raise _INVALID from exc
        return {"workspace": ref}

    async def remove(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        workspace_id = params.get("workspace_id")
        if not isinstance(workspace_id, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("workspace", mutation_id)
            self._lease.acquire("workspace", mutation_id)
            try:
                self._store.remove(workspace_id)
            finally:
                self._lease.release("workspace", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        return {"removed": True, "workspace_id": workspace_id}

    async def revalidate(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        workspace_id = params.get("workspace_id")
        if not isinstance(workspace_id, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("workspace", mutation_id)
            self._lease.acquire("workspace", mutation_id)
            try:
                # The RPC boundary is the pre-dispatch gate.  The Store still
                # accepts a lease for direct trusted composition callers.
                ref = self._store.revalidate(workspace_id)
            finally:
                self._lease.release("workspace", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except LookupError as exc:
            code = getattr(exc, "public_code", "")
            if code == "workspace_relink_required" or "relink" in str(exc).lower():
                raise _RELINK from exc
            raise _NOT_FOUND from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        return {"workspace": ref}


def _require_mutation(params: dict[str, Any]) -> str:
    mid = params.get("mutation_id")
    if not isinstance(mid, str) or not mid.strip():
        raise _INVALID
    return mid
