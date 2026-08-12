"""Host-only interactive session RPC methods (078 T026).

Dispatches solely through ``LoopPlaneHost`` / ``Session`` facades held by
``InteractionLease``. Never imports controller, gateway, or store modules.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from loopplane.host import LoopPlaneHost

try:
    from ..interaction import InteractionBusy, InteractionLease
    from ..mutation_lease import MutationLeaseBusy, ProfileMutationLease
    from ..protocol import RpcError
    from ..workspace import WorkspaceStore
except ImportError:  # pragma: no cover - script-path load
    from interaction import InteractionBusy, InteractionLease  # type: ignore[no-redef]
    from mutation_lease import (  # type: ignore[no-redef]
        MutationLeaseBusy,
        ProfileMutationLease,
    )
    from protocol import RpcError  # type: ignore[no-redef]
    from workspace import WorkspaceStore  # type: ignore[no-redef]

MethodHandler = Callable[[dict[str, Any]], Awaitable[Any]]


def _busy_error(
    *,
    owner_pane_id: str | None = None,
    owner_session_id: str | None = None,
) -> RpcError:
    extra: dict[str, Any] = {}
    if owner_pane_id is not None:
        extra["owner_pane_id"] = owner_pane_id
    if owner_session_id is not None:
        extra["owner_session_id"] = owner_session_id
    return RpcError(
        code=-32004,
        message="Busy",
        category="busy",
        retryable=False,
        message_key="desktop.error.busy",
        data=extra or None,
    )


_BUSY = _busy_error()
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
_STATE = RpcError(
    code=-32001,
    message="Invalid state",
    category="state",
    retryable=False,
    message_key="desktop.error.invalid_state",
)
_RELINK = RpcError(
    code=-32006,
    message="Workspace relink required",
    category="workspace_relink_required",
    retryable=False,
    message_key="desktop.error.workspace_relink_required",
    recovery="relink_workspace",
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


class InteractionMethods:
    """Registerable handlers for session/interaction JSON-RPC methods."""

    def __init__(
        self,
        host: LoopPlaneHost,
        lease: InteractionLease,
        *,
        working_scope: Path | None = None,
        emit_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        emit_outcome: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        workspace_store: WorkspaceStore | None = None,
        mutation_lease: ProfileMutationLease | None = None,
        principal_id: str | None = None,
        principal_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._host = host
        self._lease = lease
        self._working_scope = working_scope
        self._workspace_store = workspace_store
        self._mutation_lease = mutation_lease
        self._principal_id = principal_id
        self._principal_provider = principal_provider
        if emit_event is not None or emit_outcome is not None:
            self._lease.set_emitters(emit_event=emit_event, emit_outcome=emit_outcome)

    def _acquire_mutation(self, mutation_id: str) -> None:
        if self._mutation_lease is None:
            return
        try:
            self._mutation_lease.require_free_or_owner("interaction", mutation_id)
            self._mutation_lease.acquire("interaction", mutation_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc

    def _release_mutation(self, mutation_id: str) -> None:
        if self._mutation_lease is not None:
            self._mutation_lease.release("interaction", mutation_id)

    def _principal(self, params: Mapping[str, Any]) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        if self._principal_id is not None:
            return self._principal_id
        value = params.get("principal_id")
        return value if isinstance(value, str) else None

    def _resolve_scope(
        self, params: Mapping[str, Any], mutation_id: str
    ) -> Path | None:
        """Validate workspace immediately before create/resume (078 T046).

        Returns a trusted directory path for Host working_scope, or the
        configured default when no workspace_id is supplied.
        """

        workspace_id = params.get("workspace_id")
        if workspace_id is None:
            return self._working_scope
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise _INVALID
        if self._workspace_store is None:
            raise _INVALID
        try:
            # Prefer lease-gated revalidate when a mutation lease is wired.
            if self._mutation_lease is not None:
                self._workspace_store.revalidate(
                    workspace_id,
                    lease=self._mutation_lease,
                    lease_owner="interaction",
                    mutation_identity=mutation_id,
                )
            path = self._workspace_store.resolve_path(workspace_id)
        except MutationLeaseBusy as exc:
            raise _BUSY from exc
        except LookupError as exc:
            code = getattr(exc, "public_code", "")
            if code == "workspace_relink_required" or "relink" in str(exc).lower():
                raise _RELINK from exc
            raise _NOT_FOUND from exc
        except KeyError as exc:
            raise _NOT_FOUND from exc
        return path

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "session.createInteractive": self.create_interactive,
            "session.resumeInteractive": self.resume_interactive,
            "session.releaseInteractive": self.release_interactive,
            "interaction.submit": self.submit,
            "interaction.cancel": self.cancel,
            "interaction.answerApproval": self.answer_approval,
            "interaction.answerQuestion": self.answer_question,
        }

    async def create_interactive(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        pane_id = params.get("pane_id")
        if pane_id is not None and not isinstance(pane_id, str):
            raise _INVALID
        self._acquire_mutation(mutation_id)
        try:
            scope = self._resolve_scope(params, mutation_id)
            try:
                sub = await self._lease.create_interactive(
                    self._host,
                    pane_id=pane_id if isinstance(pane_id, str) else None,
                    working_scope=scope,
                    principal_id=self._principal(params),
                )
            except InteractionBusy as exc:
                raise _busy_error(
                    owner_pane_id=getattr(exc, "owner_pane_id", None),
                    owner_session_id=getattr(exc, "owner_session_id", None),
                ) from exc
            return {
                "session_id": sub.session_id,
                "subscription_id": sub.subscription_id,
                "pane_id": sub.pane_id,
            }
        finally:
            self._release_mutation(mutation_id)

    async def resume_interactive(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        session_id = _require_str(params, "session_id")
        pane_id = params.get("pane_id")
        if pane_id is not None and not isinstance(pane_id, str):
            raise _INVALID
        self._acquire_mutation(mutation_id)
        try:
            scope = self._resolve_scope(params, mutation_id)
            try:
                sub = await self._lease.resume_interactive(
                    self._host,
                    session_id,
                    pane_id=pane_id if isinstance(pane_id, str) else None,
                    working_scope=scope,
                    principal_id=self._principal(params),
                )
            except InteractionBusy as exc:
                raise _busy_error(
                    owner_pane_id=getattr(exc, "owner_pane_id", None),
                    owner_session_id=getattr(exc, "owner_session_id", None),
                ) from exc
            except RpcError:
                raise
            except Exception as exc:
                # Unknown session / resume fault: public-safe not_found, no traceback.
                raise _NOT_FOUND from exc
            return {
                "session_id": sub.session_id,
                "subscription_id": sub.subscription_id,
                "pane_id": sub.pane_id,
                "replay_boundary": "attached",
            }
        finally:
            self._release_mutation(mutation_id)

    async def release_interactive(self, params: dict[str, Any]) -> dict[str, Any]:
        _require_mutation_id(params)
        subscription_id = _require_str(params, "subscription_id")
        ok = await self._lease.release(subscription_id)
        if not ok:
            raise _NOT_FOUND
        return {"released": True, "subscription_id": subscription_id}

    async def submit(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        subscription_id = _require_str(params, "subscription_id")
        prompt = params.get("prompt")
        if not isinstance(prompt, str):
            raise _INVALID
        self._acquire_mutation(mutation_id)
        try:
            try:
                sub = self._lease.require_owner(subscription_id)
            except KeyError as exc:
                raise _NOT_FOUND from exc
            except InteractionBusy as exc:
                raise _busy_error(
                    owner_pane_id=getattr(exc, "owner_pane_id", None),
                    owner_session_id=getattr(exc, "owner_session_id", None),
                ) from exc
            if sub.run_active:
                raise _STATE
            sub.run_active = True
            try:
                outcome = await sub.session.submit(
                    prompt,
                    output_schema=params.get("output_schema")
                    if isinstance(params.get("output_schema"), dict)
                    else None,
                    permission_mode=params.get("permission_mode")
                    if isinstance(params.get("permission_mode"), str)
                    else None,
                )
            finally:
                sub.run_active = False

            payload = {
                "subscription_id": subscription_id,
                "session_id": sub.session_id,
                "reason": outcome.termination_reason,
                "turns": outcome.turns_taken,
            }
            await self._lease.emit_outcome(payload)
            return {
                "accepted": True,
                "subscription_id": subscription_id,
                "session_id": sub.session_id,
                "termination_reason": outcome.termination_reason,
                "turns_taken": outcome.turns_taken,
            }
        finally:
            self._release_mutation(mutation_id)

    async def cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        _require_mutation_id(params)
        subscription_id = _require_str(params, "subscription_id")
        try:
            sub = self._lease.require_owner(subscription_id)
        except KeyError as exc:
            raise _NOT_FOUND from exc
        except InteractionBusy as exc:
            raise _busy_error(
                owner_pane_id=getattr(exc, "owner_pane_id", None),
                owner_session_id=getattr(exc, "owner_session_id", None),
            ) from exc
        sub.session.cancel()
        return {
            "cancelled": True,
            "subscription_id": subscription_id,
            "session_id": sub.session_id,
        }

    async def answer_approval(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        subscription_id = _require_str(params, "subscription_id")
        request_id = _require_str(params, "request_id")
        allow = params.get("allow")
        if not isinstance(allow, bool):
            raise _INVALID
        self._acquire_mutation(mutation_id)
        try:
            try:
                sub = self._lease.require_owner(subscription_id)
            except KeyError as exc:
                raise _NOT_FOUND from exc
            except InteractionBusy as exc:
                raise _busy_error(
                    owner_pane_id=getattr(exc, "owner_pane_id", None),
                    owner_session_id=getattr(exc, "owner_session_id", None),
                ) from exc
            scope = params.get("scope", "once")
            if scope not in ("once", "session"):
                raise _INVALID
            accepted = sub.session.answer_approval(
                request_id,
                allow=allow,
                scope=scope,  # type: ignore[arg-type]
                reason=params.get("reason")
                if isinstance(params.get("reason"), str)
                else None,
            )
            return {
                "accepted": accepted,
                "subscription_id": subscription_id,
                "request_id": request_id,
            }
        finally:
            self._release_mutation(mutation_id)

    async def answer_question(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        subscription_id = _require_str(params, "subscription_id")
        request_id = _require_str(params, "request_id")
        answers = params.get("answers")
        if not isinstance(answers, list) or not all(
            isinstance(a, str) for a in answers
        ):
            raise _INVALID
        self._acquire_mutation(mutation_id)
        try:
            try:
                sub = self._lease.require_owner(subscription_id)
            except KeyError as exc:
                raise _NOT_FOUND from exc
            except InteractionBusy as exc:
                raise _busy_error(
                    owner_pane_id=getattr(exc, "owner_pane_id", None),
                    owner_session_id=getattr(exc, "owner_session_id", None),
                ) from exc
            accepted = sub.session.answer_question(request_id, answers)
            return {
                "accepted": accepted,
                "subscription_id": subscription_id,
                "request_id": request_id,
            }
        finally:
            self._release_mutation(mutation_id)
