"""Host-backed non-interactive session RPC methods (078 T042)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..projects import ProjectStore
    from ..protocol import RpcError
except ImportError:  # pragma: no cover
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
    code=-32002,
    message="Not found",
    category="not_found",
    retryable=False,
    message_key="desktop.error.not_found",
)
_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="invalid_params",
    retryable=False,
    message_key="desktop.error.invalid_params",
)


class SessionMethods:
    def __init__(
        self,
        host: LoopPlaneHost,
        lease: ProfileMutationLease,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self._host = host
        self._lease = lease
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        self._project_store = project_store

    def _principal(self) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        return self._principal_id

    def _owned_session_principal(self, session_id: str) -> tuple[bool, str | None]:
        principal_id = self._principal()
        for summary in self._host.list_sessions():
            if summary.session_id == session_id and (
                principal_id is None or summary.principal_id in (None, principal_id)
            ):
                return True, summary.principal_id
        return False, None

    def _is_owned_session(self, session_id: str) -> bool:
        return self._owned_session_principal(session_id)[0]

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "session.list": self.list_sessions,
            "session.history": self.history,
            "session.rename": self.rename,
            "session.setStarred": self.set_starred,
            "session.delete": self.delete,
            "session.fork": self.fork,
        }

    async def list_sessions(self, params: dict[str, Any]) -> dict[str, Any]:
        principal_id = self._principal()
        query = params.get("query")
        if isinstance(query, str) and query.strip():
            summaries = self._host.search_sessions(query, principal_id)
        else:
            summaries = self._host.list_sessions()
        if principal_id is not None:
            summaries = [
                s
                for s in summaries
                if getattr(s, "principal_id", None) in (None, principal_id)
            ]
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "title": getattr(s, "title", None),
                    "starred": bool(getattr(s, "starred", False)),
                    "principal_id": getattr(s, "principal_id", None),
                }
                for s in summaries
            ]
        }

    async def history(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("session_id")
        if not isinstance(session_id, str):
            raise _INVALID
        listed = await self.list_sessions({})
        summary = next(
            (s for s in listed["sessions"] if s["session_id"] == session_id),
            None,
        )
        if summary is None:
            raise _NOT_FOUND
        try:
            snap = self._host.history_snapshot(session_id)
        except Exception as exc:
            raise _NOT_FOUND from exc
        entries = []
        for item in snap:
            entries.append(
                {
                    "role": getattr(item, "role", None),
                    "text": getattr(item, "text", None)
                    or str(getattr(item, "content", "") or "")[:4096],
                }
            )
        return {"session_id": session_id, "entries": entries, "summary": summary}

    async def rename(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        session_id = params.get("session_id")
        title = params.get("title")
        if not isinstance(session_id, str) or not isinstance(title, str):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("session", mutation_id)
            self._lease.acquire("session", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            if not self._is_owned_session(session_id):
                raise _NOT_FOUND
            try:
                await self._host.set_session_title(session_id, title)
            except Exception as exc:
                raise _NOT_FOUND from exc
        finally:
            self._lease.release("session", mutation_id)
        return {"session_id": session_id, "title": title}

    async def set_starred(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        session_id = params.get("session_id")
        starred = params.get("starred")
        if not isinstance(session_id, str) or not isinstance(starred, bool):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("session", mutation_id)
            self._lease.acquire("session", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            if not self._is_owned_session(session_id):
                raise _NOT_FOUND
            try:
                await self._host.set_session_starred(session_id, starred)
            except Exception as exc:
                raise _NOT_FOUND from exc
        finally:
            self._lease.release("session", mutation_id)
        return {"session_id": session_id, "starred": starred}

    async def delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        session_id = params.get("session_id")
        if not isinstance(session_id, str):
            raise _INVALID
        # Explicit confirmation token required by contract.
        if not params.get("confirmation"):
            raise _INVALID
        try:
            self._lease.require_free_or_owner("session", mutation_id)
            self._lease.acquire("session", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            owned, session_principal = self._owned_session_principal(session_id)
            if not owned:
                raise _NOT_FOUND
            project_id = (
                self._project_store.session_project(session_id)
                if self._project_store is not None
                else None
            )
            if self._project_store is not None and project_id is not None:
                self._project_store.assign_session(None, session_id)
            try:
                deleted = self._host.bulk_delete_sessions(
                    [session_id], principal_id=session_principal
                )
                if session_id not in deleted:
                    raise LookupError("session deletion was not applied")
            except Exception as exc:
                # Unassignment is fail-safe even when session deletion is not.
                # Re-adding membership after an ambiguous artifact rollback can
                # recreate a dangling Project authority.
                raise _NOT_FOUND from exc
        finally:
            self._lease.release("session", mutation_id)
        return {"deleted": True, "session_id": session_id}

    async def fork(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation(params)
        session_id = params.get("session_id")
        if not isinstance(session_id, str):
            raise _INVALID
        if not params.get("confirmation"):
            raise _INVALID
        source_sequence = params.get("source_sequence", 0)
        if not isinstance(source_sequence, int) or source_sequence < 0:
            raise _INVALID
        try:
            self._lease.require_free_or_owner("session", mutation_id)
            self._lease.acquire("session", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        try:
            if not self._is_owned_session(session_id):
                raise _NOT_FOUND
            try:
                new_id = await self._host.fork_session(
                    session_id,
                    principal_id=self._principal(),
                    source_sequence=source_sequence,
                    title=params.get("title")
                    if isinstance(params.get("title"), str)
                    else None,
                )
            except Exception as exc:
                raise _NOT_FOUND from exc
        finally:
            self._lease.release("session", mutation_id)
        session_out = (
            new_id if isinstance(new_id, str) else getattr(new_id, "session_id", None)
        )
        return {
            "session_id": session_out,
            "source_session_id": session_id,
        }


def _require_mutation(params: dict[str, Any]) -> str:
    mid = params.get("mutation_id")
    if not isinstance(mid, str) or not mid.strip():
        raise _INVALID
    return mid
