"""Desktop sidecar capability management (083 Wave 4, T019/T021/T022).

MCP / skills / memory projections must be metadata-only field allowlists — no
endpoint, credential, header, token, owner id, raw problem text, or path ever
reaches the renderer (FR-006–FR-008, FR-018; SC-003, SC-004). Every durable
mutation takes the profile mutation lease with a main-generated mutation id
(FR-017), and a held lease refuses busy rather than queueing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from loopplane.host.capabilities import (
    CapabilityOperationResult,
    CapabilitySettingsStatus,
    ManagedMcpConfiguration,
    ManagedMemoryDetail,
    ManagedMemoryEntry,
    ManagedSkill,
    ManagedSkillDetail,
)

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from methods.capability import CapabilityMethods  # noqa: E402
from methods.inspection import InspectionMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402

pytestmark = pytest.mark.anyio

POISON_URL = "https://user:token-abc123@10.77.0.5:9999/internal/secret-path"
POISON_TEXT = r"Traceback C:\Users\hidden\profile bearer sk-live-key"
POISON_OWNER = "principal-hidden-9"
_MARKERS = ("token-abc123", "10.77.0.5", "secret-path", "hidden", "sk-live-key")


def _mcp(status: str = "unavailable") -> ManagedMcpConfiguration:
    return ManagedMcpConfiguration(
        id="mcp-1",
        name="internal tools",
        status=status,  # type: ignore[arg-type]
        tool_count=2,
        transport="http",
        url=POISON_URL,
        tools=("alpha", "beta"),
        problem=POISON_TEXT,
        owner_id=POISON_OWNER,
        actions=("open", "reconnect", "delete"),
    )


class _FakeHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.mcp_status = "unavailable"

    # --- MCP (async mutations, matching LoopPlaneHost) ---
    def list_managed_mcp(self, principal_id: str | None = None) -> tuple[Any, ...]:
        return (_mcp(self.mcp_status),)

    def get_managed_mcp(
        self, mcp_id: str, *, principal_id: str | None = None
    ) -> ManagedMcpConfiguration:
        if mcp_id != "mcp-1":
            raise KeyError(mcp_id)
        return _mcp(self.mcp_status)

    async def upsert_managed_mcp(self, **kwargs: Any) -> CapabilityOperationResult:
        self.calls.append(("upsert_managed_mcp", kwargs))
        return CapabilityOperationResult(
            ok=True, resource_id="mcp-1", status="available", message="saved"
        )

    async def reconnect_managed_mcp(
        self, mcp_id: str, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("reconnect_managed_mcp", {"mcp_id": mcp_id}))
        return CapabilityOperationResult(
            ok=False, resource_id=mcp_id, status="unavailable", message="unreachable"
        )

    async def delete_managed_mcp(
        self, mcp_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(
            ("delete_managed_mcp", {"mcp_id": mcp_id, "confirm": confirm})
        )
        return CapabilityOperationResult(
            ok=True, resource_id=mcp_id, status="available", message="deleted"
        )

    # --- Skills (sync, matching LoopPlaneHost) ---
    def list_managed_skills(self, principal_id: str | None = None) -> tuple[Any, ...]:
        return (
            ManagedSkill(
                id="skill-1",
                name="notes",
                description="take notes",
                source=POISON_TEXT,
                problem=POISON_TEXT,
                actions=("open", "delete"),
            ),
        )

    def get_managed_skill(
        self, skill_id: str, *, principal_id: str | None = None
    ) -> ManagedSkillDetail:
        return ManagedSkillDetail(
            id=skill_id,
            name="notes",
            description="take notes",
            source=POISON_TEXT,
            problem=POISON_TEXT,
            actions=("open", "delete"),
            instructions="write everything down",
        )

    def write_managed_skill(self, **kwargs: Any) -> CapabilityOperationResult:
        self.calls.append(("write_managed_skill", kwargs))
        return CapabilityOperationResult(
            ok=True, resource_id="skill-1", status="available", message="saved"
        )

    def import_managed_skill(
        self, definition: Any, *, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(("import_managed_skill", {"definition": definition}))
        return CapabilityOperationResult(
            ok=True, resource_id="skill-2", status="available", message="imported"
        )

    def delete_managed_skill(
        self, skill_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(
            ("delete_managed_skill", {"skill_id": skill_id, "confirm": confirm})
        )
        return CapabilityOperationResult(
            ok=True, resource_id=skill_id, status="available", message="deleted"
        )

    # --- Memory (sync, matching LoopPlaneHost) ---
    def list_managed_memory(
        self, *, principal_id: str | None = None
    ) -> tuple[Any, ...]:
        return (
            ManagedMemoryEntry(
                id="memory-1",
                name="prefs",
                kind="user",
                description="user prefs",
                snippet="dark theme",
                problem=POISON_TEXT,
                actions=("open", "delete"),
            ),
        )

    def get_managed_memory(
        self, memory_id: str, *, principal_id: str | None = None
    ) -> ManagedMemoryDetail:
        return ManagedMemoryDetail(
            id=memory_id,
            name="prefs",
            kind="user",
            description="user prefs",
            snippet="dark theme",
            problem=POISON_TEXT,
            actions=("open", "delete"),
            content="prefers dark theme",
        )

    def write_managed_memory(self, **kwargs: Any) -> CapabilityOperationResult:
        self.calls.append(("write_managed_memory", kwargs))
        return CapabilityOperationResult(
            ok=True, resource_id="memory-1", status="available", message="saved"
        )

    def delete_managed_memory(
        self, memory_id: str, *, confirm: bool, principal_id: str | None = None
    ) -> CapabilityOperationResult:
        self.calls.append(
            ("delete_managed_memory", {"memory_id": memory_id, "confirm": confirm})
        )
        return CapabilityOperationResult(
            ok=True, resource_id=memory_id, status="available", message="deleted"
        )

    # capabilities_list probes (InspectionMethods reuse in card tests). The
    # REAL dataclass is used so a field-name drift fails here, not in the wild.
    mcp_policy_available = False

    def capability_settings_status(
        self, *, principal_id: str | None = None
    ) -> CapabilitySettingsStatus:
        return CapabilitySettingsStatus(
            storage_available=True,
            mutations_enabled=True,
            runtime_activation_enabled=False,
            mcp_endpoint_policy_available=self.mcp_policy_available,
            schedule_runner_available=False,
        )

    def monthly_spend(self, principal_id: str) -> None:
        return None


def _methods(
    host: _FakeHost | None = None,
    lease: ProfileMutationLease | None = None,
) -> CapabilityMethods:
    return CapabilityMethods(
        host or _FakeHost(),  # type: ignore[arg-type]
        principal_provider=lambda: "principal-1",
        mutation_lease=lease,
    )


def _assert_marker_free(payload: Any) -> None:
    blob = str(payload)
    for marker in _MARKERS:
        assert marker not in blob, f"leaked {marker!r}"


async def test_mcp_list_projects_metadata_only() -> None:
    result = await _methods().mcp_list({})
    (item,) = result["items"]
    assert set(item) == {
        "id",
        "name",
        "status",
        "tool_count",
        "transport",
        "tools",
        "scope",
        "actions",
        "reason",
    }
    assert item["status"] == "unavailable"
    assert isinstance(item["reason"], str) and item["reason"]
    _assert_marker_free(result)


async def test_mcp_get_omits_endpoint_problem_and_owner() -> None:
    result = await _methods().mcp_get({"mcp_id": "mcp-1"})
    assert result["name"] == "internal tools"
    assert result["tools"] == ["alpha", "beta"]
    assert "url" not in result and "problem" not in result and "owner_id" not in result
    _assert_marker_free(result)
    host = _FakeHost()
    host.mcp_status = "available"
    available = await _methods(host).mcp_get({"mcp_id": "mcp-1"})
    assert available["reason"] is None


async def test_mcp_mutations_require_a_mutation_id() -> None:
    methods = _methods()
    for call, params in (
        (methods.mcp_upsert, {"name": "x", "transport": "http", "url": "https://a"}),
        (methods.mcp_delete, {"mcp_id": "mcp-1"}),
        (methods.mcp_reconnect, {"mcp_id": "mcp-1"}),
    ):
        with pytest.raises(RpcError) as exc:
            await call(dict(params))
        assert exc.value.category == "invalid_params"


async def test_mutation_refused_busy_while_lease_is_held() -> None:
    lease = ProfileMutationLease()
    lease.acquire("backup", "other-op")
    methods = _methods(lease=lease)
    with pytest.raises(RpcError) as exc:
        await methods.mcp_upsert(
            {
                "mutation_id": "m-1",
                "name": "x",
                "transport": "http",
                "url": "https://a",
            }
        )
    assert exc.value.category == "busy"
    assert not methods._host.calls  # type: ignore[attr-defined]


async def test_mcp_upsert_delegates_and_answers_public_result() -> None:
    host = _FakeHost()
    lease = ProfileMutationLease()
    result = await _methods(host, lease).mcp_upsert(
        {
            "mutation_id": "m-2",
            "name": "srv",
            "transport": "sse",
            "url": "https://mcp.example/sse",
        }
    )
    assert result == {"ok": True, "message": "saved"}
    name, kwargs = host.calls[0]
    assert name == "upsert_managed_mcp"
    assert kwargs["name"] == "srv"
    assert kwargs["transport"] == "sse"
    assert kwargs["url"] == "https://mcp.example/sse"
    assert not lease.held()


async def test_mcp_upsert_rejects_unknown_transport() -> None:
    with pytest.raises(RpcError) as exc:
        await _methods().mcp_upsert(
            {"mutation_id": "m-3", "name": "srv", "transport": "stdio", "url": "x"}
        )
    assert exc.value.category == "invalid_params"


async def test_mcp_delete_confirms_and_reconnect_reports_result() -> None:
    host = _FakeHost()
    deleted = await _methods(host).mcp_delete({"mutation_id": "m-4", "mcp_id": "mcp-1"})
    assert deleted["ok"] is True
    assert host.calls[-1][1]["confirm"] is True
    reconnected = await _methods(host).mcp_reconnect(
        {"mutation_id": "m-5", "mcp_id": "mcp-1"}
    )
    assert reconnected == {"ok": False, "message": "unreachable"}


async def test_skill_detail_returns_instructions_never_source() -> None:
    listing = await _methods().skill_list({})
    (record,) = listing["items"]
    assert "source" not in record and "problem" not in record
    detail = await _methods().skill_get({"skill_id": "skill-1"})
    assert detail["instructions"] == "write everything down"
    assert "source" not in detail
    _assert_marker_free(listing)
    _assert_marker_free(detail)


async def test_skill_write_import_delete_take_the_lease() -> None:
    host = _FakeHost()
    lease = ProfileMutationLease()
    methods = _methods(host, lease)
    wrote = await methods.skill_write(
        {
            "mutation_id": "m-6",
            "name": "notes",
            "description": "",
            "instructions": "write",
        }
    )
    assert wrote["ok"] is True
    imported = await methods.skill_import(
        {
            "mutation_id": "m-7",
            "name": "notes-2",
            "description": "",
            "instructions": "copy",
        }
    )
    assert imported == {"ok": True, "message": "imported"}
    assert host.calls[-1][1]["definition"] == {
        "name": "notes-2",
        "description": "",
        "instructions": "copy",
    }
    removed = await methods.skill_delete({"mutation_id": "m-8", "skill_id": "skill-1"})
    assert removed["ok"] is True
    assert host.calls[-1][1]["confirm"] is True
    assert not lease.held()


async def test_memory_projection_and_mutations() -> None:
    host = _FakeHost()
    listing = await _methods(host).memory_list({})
    (record,) = listing["items"]
    assert record["kind"] == "user"
    assert record["snippet"] == "dark theme"
    assert "problem" not in record
    _assert_marker_free(listing)

    detail = await _methods(host).memory_get({"memory_id": "memory-1"})
    assert detail["content"] == "prefers dark theme"
    _assert_marker_free(detail)

    wrote = await _methods(host).memory_write(
        {
            "mutation_id": "m-9",
            "name": "prefs",
            "kind": "user",
            "description": "",
            "content": "prefers dark theme",
        }
    )
    assert wrote["ok"] is True
    assert host.calls[-1][1]["kind"] == "user"

    removed = await _methods(host).memory_delete(
        {"mutation_id": "m-10", "memory_id": "memory-1"}
    )
    assert removed["ok"] is True
    assert host.calls[-1][1]["confirm"] is True


async def test_read_failures_map_to_public_catalogue() -> None:
    class _BrokenHost(_FakeHost):
        def list_managed_mcp(self, principal_id: str | None = None) -> tuple[Any, ...]:
            raise RuntimeError(POISON_TEXT)

    with pytest.raises(RpcError) as exc:
        await _methods(_BrokenHost()).mcp_list({})
    assert exc.value.category == "unavailable"
    with pytest.raises(RpcError) as missing:
        await _methods().mcp_get({"mcp_id": "mcp-404"})
    assert missing.value.category == "not_found"


async def test_connected_mcp_carries_no_unavailable_reason() -> None:
    host = _FakeHost()
    host.mcp_status = "connected"
    result = await _methods(host).mcp_get({"mcp_id": "mcp-1"})
    assert result["status"] == "connected"
    assert result["reason"] is None


async def test_capabilities_list_cards_align_availability_and_reason() -> None:
    async def cards_for(host: _FakeHost) -> dict[str, Any]:
        inspection = InspectionMethods(
            host,  # type: ignore[arg-type]
            principal_provider=lambda: "principal-1",
        )
        listed = await inspection.capabilities_list({})
        return {card["id"]: card for card in listed["capabilities"]}

    # Real settings status without an MCP endpoint policy -> unavailable card.
    without_policy = await cards_for(_FakeHost())
    assert without_policy["mcp"]["available"] is False
    assert without_policy["mcp"]["status"] == "unavailable"
    assert (
        isinstance(without_policy["mcp"]["reason"], str)
        and without_policy["mcp"]["reason"]
    )
    for domain in ("memory", "skills"):
        assert without_policy[domain]["available"] is True
        assert without_policy[domain]["status"] == "available"
        assert without_policy[domain]["reason"] is None

    # Real settings status WITH the endpoint policy -> the card lights up.
    enabled_host = _FakeHost()
    enabled_host.mcp_policy_available = True
    with_policy = await cards_for(enabled_host)
    assert with_policy["mcp"]["available"] is True
    assert with_policy["mcp"]["status"] == "available"
    assert with_policy["mcp"]["reason"] is None
