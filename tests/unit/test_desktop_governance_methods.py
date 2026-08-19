"""Desktop sidecar governance surface (083 Wave 5, T027/T028).

Schedules / workspace contexts / model default over public ``LoopPlaneHost``
methods only. Projections are metadata-only allowlists (no owner id, problem
text, or timestamp), every durable mutation takes the profile mutation lease
under a main-generated mutation id, and each domain reports availability
through the ``capabilities.list`` cards (FR-009–FR-012, FR-015–FR-018).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from loopplane.host.capabilities import (
    CapabilityOperationResult,
    CapabilitySettingsStatus,
    ManagedSchedule,
    ModelDefault,
    SessionContextBinding,
    WorkspaceContext,
)

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from methods.governance import GovernanceMethods  # noqa: E402
from methods.inspection import InspectionMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402

pytestmark = pytest.mark.anyio

POISON_TEXT = r"Traceback C:\Users\hidden\profile bearer sk-live-key"
POISON_OWNER = "principal-hidden-9"
_MARKERS = ("hidden", "sk-live-key", POISON_OWNER)


def _ok(resource_id: str, message: str = "saved") -> CapabilityOperationResult:
    return CapabilityOperationResult(
        ok=True, resource_id=resource_id, status="available", message=message
    )


class _FakeHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.schedule_runner = False
        self.storage_available = True
        self.model_default_status = "unavailable"

    # --- Schedules (sync, matching LoopPlaneHost) ---
    def list_managed_schedules(
        self, principal_id: str | None = None
    ) -> tuple[Any, ...]:
        return (
            ManagedSchedule(
                id="schedule-1",
                name="daily",
                description="daily notes",
                trigger="0 9 * * *",
                enabled=True,
                instruction="refresh notes",
                status="disabled",
                problem=POISON_TEXT,
                owner_id=POISON_OWNER,
                actions=("open", "run_now", "disable", "delete"),
            ),
        )

    def get_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> ManagedSchedule:
        if schedule_id != "schedule-1":
            raise KeyError(schedule_id)
        return self.list_managed_schedules()[0]

    def upsert_managed_schedule(self, **kwargs: Any) -> CapabilityOperationResult:
        self.calls.append(("upsert_managed_schedule", kwargs))
        return _ok("schedule-1")

    def enable_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("enable_managed_schedule", {"schedule_id": schedule_id}))
        return _ok(schedule_id, "enabled")

    def disable_managed_schedule(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("disable_managed_schedule", {"schedule_id": schedule_id}))
        return _ok(schedule_id, "disabled")

    def run_managed_schedule_now(
        self, schedule_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("run_managed_schedule_now", {"schedule_id": schedule_id}))
        return CapabilityOperationResult(
            ok=False, resource_id=schedule_id, status="unavailable", message="no runner"
        )

    def delete_managed_schedule(
        self, schedule_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(
            (
                "delete_managed_schedule",
                {"schedule_id": schedule_id, "confirm": confirm},
            )
        )
        return _ok(schedule_id, "deleted")

    # --- Workspace contexts (sync except bind) ---
    def list_workspace_contexts(
        self, principal_id: str | None = None
    ) -> tuple[Any, ...]:
        return (
            WorkspaceContext(
                id="context-1",
                name="Docs",
                description="docs repo",
                workspace_label="docs-repo",
                problem=POISON_TEXT,
                owner_id=POISON_OWNER,
                actions=("open", "bind", "delete"),
            ),
        )

    def get_workspace_context(
        self, context_id: str, *, principal_id: str | None = None
    ) -> WorkspaceContext:
        if context_id != "context-1":
            raise KeyError(context_id)
        return self.list_workspace_contexts()[0]

    def upsert_workspace_context(self, **kwargs: Any) -> CapabilityOperationResult:
        self.calls.append(("upsert_workspace_context", kwargs))
        return _ok("context-1")

    async def bind_session_context(
        self, session_id: str, context_id: str, *, principal_id: str | None = None
    ) -> SessionContextBinding:
        self.calls.append(
            (
                "bind_session_context",
                {"session_id": session_id, "context_id": context_id},
            )
        )
        return SessionContextBinding(
            session_id=session_id,
            context_id=context_id,
            name="Docs",
            workspace_label="docs-repo",
        )

    def delete_workspace_context(
        self, context_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(
            (
                "delete_workspace_context",
                {"context_id": context_id, "confirm": confirm},
            )
        )
        return _ok(context_id, "deleted")

    # --- Model default ---
    def model_default(
        self,
        principal_id: str | None = None,
        *,
        available_models: Any = None,
    ) -> ModelDefault:
        self.calls.append(("model_default", {"available_models": available_models}))
        return ModelDefault(
            model_id="model-x" if self.model_default_status == "available" else None,
            label="Model X" if self.model_default_status == "available" else None,
            status=self.model_default_status,  # type: ignore[arg-type]
            problem=POISON_TEXT,
        )

    def set_model_default(
        self,
        model_id: str,
        *,
        available_models: Any,
        principal_id: str | None = None,
    ) -> CapabilityOperationResult:
        self.calls.append(
            (
                "set_model_default",
                {"model_id": model_id, "available_models": available_models},
            )
        )
        return _ok(model_id)

    def clear_model_default(
        self, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("clear_model_default", {}))
        return _ok("model-default", "cleared")

    # capabilities_list probes (real dataclass so field drift fails here)
    mcp_policy_available = False

    def capability_settings_status(
        self, *, principal_id: str | None = None
    ) -> CapabilitySettingsStatus:
        return CapabilitySettingsStatus(
            storage_available=self.storage_available,
            mutations_enabled=True,
            runtime_activation_enabled=False,
            mcp_endpoint_policy_available=self.mcp_policy_available,
            schedule_runner_available=self.schedule_runner,
        )

    def monthly_spend(self, principal_id: str) -> None:
        return None


def _methods(
    host: _FakeHost | None = None,
    lease: ProfileMutationLease | None = None,
    configured_model_id: str | None = "model-x",
) -> GovernanceMethods:
    return GovernanceMethods(
        host or _FakeHost(),  # type: ignore[arg-type]
        principal_provider=lambda: "principal-1",
        mutation_lease=lease,
        configured_model_id=configured_model_id,
    )


def _assert_marker_free(payload: Any) -> None:
    blob = str(payload)
    for marker in _MARKERS:
        assert marker not in blob, f"leaked {marker!r}"


async def test_schedule_list_projects_metadata_only() -> None:
    result = await _methods().schedule_list({})
    (item,) = result["items"]
    assert set(item) == {
        "id",
        "name",
        "description",
        "trigger",
        "enabled",
        "instruction",
        "status",
        "scope",
        "actions",
        "reason",
    }
    assert item["trigger"] == "0 9 * * *"
    assert item["reason"] is None  # "disabled" is a normal state, not unavailable
    _assert_marker_free(result)


async def test_schedule_mutations_delegate_with_lease() -> None:
    host = _FakeHost()
    lease = ProfileMutationLease()
    methods = _methods(host, lease)
    upserted = await methods.schedule_upsert(
        {
            "mutation_id": "m-1",
            "name": "daily",
            "description": "",
            "trigger": "0 9 * * *",
            "instruction": "refresh",
            "enabled": True,
        }
    )
    assert upserted == {"ok": True, "message": "saved"}
    assert host.calls[-1][1]["trigger"] == "0 9 * * *"
    assert host.calls[-1][1]["enabled"] is True

    for call, key in (
        (methods.schedule_enable, "enable_managed_schedule"),
        (methods.schedule_disable, "disable_managed_schedule"),
        (methods.schedule_run_now, "run_managed_schedule_now"),
    ):
        await call({"mutation_id": "m-2", "schedule_id": "schedule-1"})
        assert host.calls[-1][0] == key

    removed = await methods.schedule_delete(
        {"mutation_id": "m-3", "schedule_id": "schedule-1"}
    )
    assert removed["ok"] is True
    assert host.calls[-1][1]["confirm"] is True
    assert not lease.held()


async def test_schedule_mutation_requires_mutation_id_and_refuses_busy() -> None:
    with pytest.raises(RpcError) as exc:
        await _methods().schedule_enable({"schedule_id": "schedule-1"})
    assert exc.value.category == "invalid_params"

    lease = ProfileMutationLease()
    lease.acquire("backup", "other-op")
    with pytest.raises(RpcError) as busy:
        await _methods(lease=lease).schedule_delete(
            {"mutation_id": "m-4", "schedule_id": "schedule-1"}
        )
    assert busy.value.category == "busy"


async def test_context_projection_and_bind() -> None:
    host = _FakeHost()
    listing = await _methods(host).context_list({})
    (record,) = listing["items"]
    assert set(record) == {
        "id",
        "name",
        "description",
        "workspace_label",
        "status",
        "scope",
        "actions",
        "reason",
    }
    _assert_marker_free(listing)

    bound = await _methods(host).context_bind(
        {"mutation_id": "m-5", "session_id": "s-1", "context_id": "context-1"}
    )
    assert bound == {
        "session_id": "s-1",
        "context_id": "context-1",
        "name": "Docs",
        "workspace_label": "docs-repo",
        "status": "available",
    }
    assert host.calls[-1][0] == "bind_session_context"

    removed = await _methods(host).context_delete(
        {"mutation_id": "m-6", "context_id": "context-1"}
    )
    assert removed["ok"] is True
    assert host.calls[-1][1]["confirm"] is True

    with pytest.raises(RpcError) as missing:
        await _methods(host).context_get({"context_id": "context-404"})
    assert missing.value.category == "not_found"


async def test_model_default_get_carries_single_entry_catalog() -> None:
    host = _FakeHost()
    host.model_default_status = "available"
    result = await _methods(host).model_default_get({})
    assert result["models"] == [{"id": "model-x", "label": "model-x"}]
    assert result["default"] == {
        "model_id": "model-x",
        "label": "Model X",
        "status": "available",
    }
    _assert_marker_free(result)
    # The caller-supplied catalog reached the host (it validates against it).
    assert host.calls[-1][1]["available_models"] == {"model-x": "model-x"}


async def test_model_default_without_provider_answers_empty_catalog() -> None:
    host = _FakeHost()
    result = await _methods(host, configured_model_id=None).model_default_get({})
    assert result["models"] == []
    assert result["default"]["status"] == "unavailable"
    # GET must pass the empty catalog rather than None: the host's catalog
    # check is what turns a stale stored default into "fallback" here.
    assert host.calls[-1][1]["available_models"] == {}


async def test_mutation_failure_still_releases_the_lease() -> None:
    class _BrokenHost(_FakeHost):
        def upsert_managed_schedule(self, **kwargs: Any) -> CapabilityOperationResult:
            raise RuntimeError(POISON_TEXT)

    lease = ProfileMutationLease()
    with pytest.raises(RpcError) as exc:
        await _methods(_BrokenHost(), lease).schedule_upsert(
            {
                "mutation_id": "m-err",
                "name": "daily",
                "description": "",
                "trigger": "0 9 * * *",
                "instruction": "refresh",
                "enabled": True,
            }
        )
    assert exc.value.category == "unavailable"
    assert not lease.held()


async def test_model_default_set_and_clear_take_the_lease() -> None:
    host = _FakeHost()
    lease = ProfileMutationLease()
    methods = _methods(host, lease)
    set_result = await methods.model_default_set(
        {"mutation_id": "m-7", "model_id": "model-x"}
    )
    assert set_result["ok"] is True
    assert host.calls[-1][1]["available_models"] == {"model-x": "model-x"}
    cleared = await methods.model_default_clear({"mutation_id": "m-8"})
    assert cleared == {"ok": True, "message": "cleared"}
    assert not lease.held()


async def test_read_failures_map_to_public_catalogue() -> None:
    class _BrokenHost(_FakeHost):
        def list_managed_schedules(
            self, principal_id: str | None = None
        ) -> tuple[Any, ...]:
            raise RuntimeError(POISON_TEXT)

    with pytest.raises(RpcError) as exc:
        await _methods(_BrokenHost()).schedule_list({})
    assert exc.value.category == "unavailable"


async def test_capabilities_list_gains_governance_cards() -> None:
    async def cards_for(
        host: _FakeHost, configured_model_id: str | None
    ) -> dict[str, Any]:
        inspection = InspectionMethods(
            host,  # type: ignore[arg-type]
            principal_provider=lambda: "principal-1",
            configured_model_id=configured_model_id,
        )
        listed = await inspection.capabilities_list({})
        return {card["id"]: card for card in listed["capabilities"]}

    bare = await cards_for(_FakeHost(), None)
    assert bare["schedules"]["available"] is False
    assert isinstance(bare["schedules"]["reason"], str)
    assert bare["contexts"]["available"] is True
    assert bare["contexts"]["reason"] is None
    assert bare["model_default"]["available"] is False
    assert isinstance(bare["model_default"]["reason"], str)

    enabled = _FakeHost()
    enabled.schedule_runner = True
    lit = await cards_for(enabled, "model-x")
    assert lit["schedules"]["available"] is True
    assert lit["schedules"]["reason"] is None
    assert lit["model_default"]["available"] is True
    assert lit["model_default"]["reason"] is None

    storageless = _FakeHost()
    storageless.storage_available = False
    dark = await cards_for(storageless, None)
    assert dark["contexts"]["available"] is False
    assert isinstance(dark["contexts"]["reason"], str)
