"""Host-only governance RPC: schedules, workspace contexts, model default
(083 Wave 5, T028).

Public ``LoopPlaneHost`` methods only. Projections are metadata-only
allowlists (no owner id, problem text, or timestamp); every durable mutation
takes the profile mutation lease under a main-generated mutation id
(FR-009–FR-012, FR-015–FR-018). The model-default catalog is the configured
provider's single model id — the host validates a set against the caller's
catalog, matching how Web supplies one (FR-011).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

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
_UNAVAILABLE = RpcError(
    code=-32008,
    message="Unavailable",
    category="unavailable",
    retryable=False,
    message_key="desktop.error.unavailable",
)

_UNAVAILABLE_REASON = "capability.unavailable"


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


def _optional_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    return value if isinstance(value, str) else ""


def _status_and_reason(record: Any) -> tuple[str, str | None]:
    # Only an explicit "unavailable" earns the reason — "disabled" is a normal
    # schedule state, and an unknown future status must not be mislabeled.
    status = str(getattr(record, "status", "unknown") or "unknown")
    return status, _UNAVAILABLE_REASON if status == "unavailable" else None


def _schedule_view(record: Any) -> dict[str, Any]:
    status, reason = _status_and_reason(record)
    return {
        "id": str(record.id),
        "name": str(record.name),
        "description": str(getattr(record, "description", "") or ""),
        "trigger": str(getattr(record, "trigger", "") or ""),
        "enabled": bool(getattr(record, "enabled", False)),
        "instruction": str(getattr(record, "instruction", "") or ""),
        "status": status,
        "scope": str(getattr(record, "scope", "owned") or "owned"),
        "actions": [str(a) for a in (getattr(record, "actions", ()) or ())],
        "reason": reason,
    }


def _context_view(record: Any) -> dict[str, Any]:
    status, reason = _status_and_reason(record)
    return {
        "id": str(record.id),
        "name": str(record.name),
        "description": str(getattr(record, "description", "") or ""),
        "workspace_label": str(getattr(record, "workspace_label", "") or ""),
        "status": status,
        "scope": str(getattr(record, "scope", "owned") or "owned"),
        "actions": [str(a) for a in (getattr(record, "actions", ()) or ())],
        "reason": reason,
    }


def _binding_view(binding: Any) -> dict[str, Any]:
    return {
        "session_id": str(getattr(binding, "session_id", "") or ""),
        "context_id": str(getattr(binding, "context_id", "") or ""),
        "name": str(getattr(binding, "name", "") or ""),
        "workspace_label": str(getattr(binding, "workspace_label", "") or ""),
        "status": str(getattr(binding, "status", "unknown") or "unknown"),
    }


def _model_default_view(record: Any) -> dict[str, Any]:
    model_id = getattr(record, "model_id", None)
    label = getattr(record, "label", None)
    return {
        "model_id": str(model_id) if model_id else None,
        "label": str(label) if label else None,
        "status": str(getattr(record, "status", "unknown") or "unknown"),
    }


def _operation_view(result: Any) -> dict[str, Any]:
    return {
        "ok": bool(getattr(result, "ok", False)),
        "message": str(getattr(result, "message", "") or ""),
    }


class GovernanceMethods:
    """Registerable handlers for schedule / context / model-default RPC."""

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

    def _principal(self) -> str | None:
        if self._principal_provider is not None:
            return self._principal_provider()
        return self._principal_id

    def _catalog(self) -> dict[str, str]:
        # Follows the provider *configuration* (ADR 0016: saving does not
        # verify; a bad key surfaces on the first reply), so the catalog can
        # name a model the runtime failed to build — same posture as
        # providers.get. An unconfigured provider yields an empty catalog.
        if not self._configured_model_id:
            return {}
        return {self._configured_model_id: self._configured_model_id}

    def handlers(self) -> dict[str, MethodHandler]:
        return {
            "schedule.list": self.schedule_list,
            "schedule.get": self.schedule_get,
            "schedule.upsert": self.schedule_upsert,
            "schedule.enable": self.schedule_enable,
            "schedule.disable": self.schedule_disable,
            "schedule.runNow": self.schedule_run_now,
            "schedule.delete": self.schedule_delete,
            "context.list": self.context_list,
            "context.get": self.context_get,
            "context.upsert": self.context_upsert,
            "context.bind": self.context_bind,
            "context.delete": self.context_delete,
            "modelDefault.get": self.model_default_get,
            "modelDefault.set": self.model_default_set,
            "modelDefault.clear": self.model_default_clear,
        }

    # --- lease discipline (FR-017) ---

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

    # --- Schedules (FR-009) ---

    async def schedule_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            records = self._host.list_managed_schedules(self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {"items": [_schedule_view(record) for record in records]}

    async def schedule_get(self, params: dict[str, Any]) -> dict[str, Any]:
        schedule_id = _require_str(params, "schedule_id")
        try:
            record = self._host.get_managed_schedule(
                schedule_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _NOT_FOUND from exc
        return _schedule_view(record)

    async def schedule_upsert(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        trigger = _require_str(params, "trigger")
        instruction = _optional_str(params, "instruction")
        description = _optional_str(params, "description")
        enabled = bool(params.get("enabled", True))
        self._acquire(mutation_id)
        try:
            result = self._host.upsert_managed_schedule(
                name=name,
                description=description,
                trigger=trigger,
                instruction=instruction,
                enabled=enabled,
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def _schedule_action(
        self,
        params: dict[str, Any],
        action: Callable[..., Any],
    ) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        schedule_id = _require_str(params, "schedule_id")
        self._acquire(mutation_id)
        try:
            result = action(schedule_id, principal_id=self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def schedule_enable(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._schedule_action(params, self._host.enable_managed_schedule)

    async def schedule_disable(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._schedule_action(params, self._host.disable_managed_schedule)

    async def schedule_run_now(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._schedule_action(params, self._host.run_managed_schedule_now)

    async def schedule_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        schedule_id = _require_str(params, "schedule_id")
        self._acquire(mutation_id)
        try:
            result = self._host.delete_managed_schedule(
                schedule_id, confirm=True, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    # --- Workspace contexts (FR-010) ---

    async def context_list(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        try:
            records = self._host.list_workspace_contexts(self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {"items": [_context_view(record) for record in records]}

    async def context_get(self, params: dict[str, Any]) -> dict[str, Any]:
        context_id = _require_str(params, "context_id")
        try:
            record = self._host.get_workspace_context(
                context_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _NOT_FOUND from exc
        return _context_view(record)

    async def context_upsert(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        name = _require_str(params, "name")
        workspace_label = _require_str(params, "workspace_label")
        description = _optional_str(params, "description")
        self._acquire(mutation_id)
        try:
            result = self._host.upsert_workspace_context(
                name=name,
                description=description,
                workspace_label=workspace_label,
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def context_bind(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        session_id = _require_str(params, "session_id")
        context_id = _require_str(params, "context_id")
        self._acquire(mutation_id)
        try:
            binding = await self._host.bind_session_context(
                session_id, context_id, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _binding_view(binding)

    async def context_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        context_id = _require_str(params, "context_id")
        self._acquire(mutation_id)
        try:
            result = self._host.delete_workspace_context(
                context_id, confirm=True, principal_id=self._principal()
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    # --- Model default (FR-011) ---

    async def model_default_get(self, params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        catalog = self._catalog()
        try:
            # Always pass the catalog — even empty — so GET and SET agree:
            # with no provider a stale stored default answers "fallback",
            # never "available" (None would skip the host's catalog check).
            record = self._host.model_default(
                self._principal(),
                available_models=catalog,
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        return {
            "default": _model_default_view(record),
            "models": [
                {"id": model_id, "label": label} for model_id, label in catalog.items()
            ],
        }

    async def model_default_set(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        model_id = _require_str(params, "model_id")
        self._acquire(mutation_id)
        try:
            result = self._host.set_model_default(
                model_id,
                available_models=self._catalog(),
                principal_id=self._principal(),
            )
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)

    async def model_default_clear(self, params: dict[str, Any]) -> dict[str, Any]:
        mutation_id = _require_mutation_id(params)
        self._acquire(mutation_id)
        try:
            result = self._host.clear_model_default(principal_id=self._principal())
        except Exception as exc:
            raise _UNAVAILABLE from exc
        finally:
            self._release(mutation_id)
        return _operation_view(result)
