"""Host-only slash commands over the shared CommandRegistry (083 Wave 6,
T033; ADR 0017).

The sidecar is the registry's third host-UX consumer beside the CLI and the
web/API host: one ``command.execute`` method dispatches a leading-``/`` line
against public host seams only — no model round-trip, no Gateway invocation,
no Event Bus emission (FR-013). Dispatch never raises; an unknown command or a
failing seam answers the registry's fixed public text (FR-014, FR-018). Only
``/compact`` mutates (the loop's compaction seam), so the whole method runs
under the profile mutation lease with a main-generated mutation id, matching
the 078 ``capabilities.invokeAction`` precedent (FR-017).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from loopplane.commands import CommandContext, default_registry
from loopplane.host import LoopPlaneHost

try:
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..protocol import RpcError
except ImportError:  # pragma: no cover - script-path load
    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
    from protocol import RpcError  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]

_INVALID = RpcError(
    code=-32602,
    message="Invalid params",
    category="invalid_params",
    retryable=False,
    message_key="desktop.error.invalid_params",
)
_NOT_FOUND = RpcError(
    code=-32002,
    message="Not found",
    category="not_found",
    retryable=False,
    message_key="desktop.error.not_found",
)
_BUSY = RpcError(
    code=-32004,
    message="Busy",
    category="busy",
    retryable=False,
    message_key="desktop.error.busy",
)


def _require_mutation_id(params: Mapping[str, Any]) -> str:
    mid = params.get("mutation_id")
    if not isinstance(mid, str) or not mid.strip():
        raise _INVALID
    return mid


def _require_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _INVALID
    return value


class CommandMethods:
    """Registerable handler for the shared slash-command registry."""

    def __init__(
        self,
        host: LoopPlaneHost,
        *,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
        mutation_lease: ProfileMutationLease | None = None,
        configured_model_id: str | None = None,
    ) -> None:
        self._host = host
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        self._mutation_lease = mutation_lease
        self._configured_model_id = configured_model_id
        self._registry = default_registry()

    def _principal(self) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        return self._principal_id

    def _is_owned_session(self, session_id: str) -> bool:
        principal_id = self._principal()
        return any(
            summary.session_id == session_id
            and (principal_id is None or summary.principal_id in (None, principal_id))
            for summary in self._host.list_sessions()
        )

    def handlers(self) -> dict[str, MethodHandler]:
        return {"command.execute": self.execute}

    def _acquire(self, mutation_id: str) -> None:
        if self._mutation_lease is None:
            return
        try:
            self._mutation_lease.require_free_or_owner("capability", mutation_id)
            self._mutation_lease.acquire("capability", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc

    def _release(self, mutation_id: str) -> None:
        if self._mutation_lease is None:
            return
        self._mutation_lease.release("capability", mutation_id)

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        text = _require_str(params, "text")
        session_id = params.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise _INVALID
        if isinstance(session_id, str) and session_id.strip():
            if not self._is_owned_session(session_id):
                raise _NOT_FOUND
        else:
            session_id = None
        self._acquire(mutation_id)
        try:
            context = CommandContext(
                host=self._host,
                principal_id=self._principal() or "",
                session_id=session_id,
                models=(
                    (self._configured_model_id,) if self._configured_model_id else ()
                ),
            )
            # dispatch never raises: unknown commands and failing seams answer
            # the registry's fixed public text.
            result = self._registry.dispatch(text, context)
        finally:
            self._release(mutation_id)
        return {"kind": result.kind, "text": result.text}
