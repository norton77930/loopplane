"""Public-safety routing over current Desktop product surfaces (078 T091).

T010 proved the scanner itself distinguishes content from secondary surfaces.
This module routes synthetic markers through the **product** code that renders
each secondary surface — the JSON-RPC dispatcher's error envelope, the fixed
public error catalogue, the backup disclosure, and the portable archive
manifest — and asserts none of them disclose LoopPlane-owned secrets, private
paths, rules, PIDs, or raw errors, while authorized conversation content
survives losslessly inside the archived content entry.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.public_safety import (
    AUTHORIZED_MODEL_CONTENT_MARKER,
    AUTHORIZED_USER_CONTENT_MARKER,
    LOOPPLANE_PATH_MARKER,
    LOOPPLANE_SECRET_MARKER,
    SurfacePayload,
    all_prohibited_secondary_markers,
    assert_content_surface_may_retain,
    assert_secondary_surface_clean,
    scan_secondary_surfaces,
)

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from archive import create_portable_archive, validate_archive  # noqa: E402
from backup import describe_backup  # noqa: E402
from dispatcher import Dispatcher  # noqa: E402
from protocol import (  # noqa: E402
    INTERNAL_FAILURE,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
    PROTOCOL_NAME,
    RUNTIME_EVENT_SCHEMA,
)

INITIALIZE_PARAMS = {
    "protocol": {
        "name": PROTOCOL_NAME,
        "major": PROTOCOL_MAJOR,
        "minor": PROTOCOL_MINOR,
    },
    "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
    "client": {"name": "public-safety-routing", "version": "0"},
    "requested_capabilities": [],
}

POISONED = " | ".join(all_prohibited_secondary_markers())


def _frame(id_: str, method: str, params: dict[str, Any]) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params})


async def _initialized(methods: dict[str, Any]) -> Dispatcher:
    dispatcher = Dispatcher(methods=methods)
    await dispatcher.handle_frame(_frame("init", "initialize", INITIALIZE_PARAMS))
    return dispatcher


@pytest.mark.anyio
async def test_rpc_error_envelope_discloses_no_raw_handler_failure() -> None:
    """A handler failure carrying every prohibited marker must not reach the wire."""

    async def failing(_params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(POISONED)

    # Premise: this exact failure text is detectable on a secondary surface, so a
    # clean envelope below is a real result rather than an unscanned one.
    assert scan_secondary_surfaces([SurfacePayload(kind="rpc_error", text=POISONED)])

    dispatcher = await _initialized({"session.list": failing})
    responses = await dispatcher.handle_frame(_frame("r1", "session.list", {}))

    assert responses, "the dispatcher must answer a failed request"
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))
    assert responses[0]["error"]["data"]["messageKey"] == INTERNAL_FAILURE.message_key


@pytest.mark.anyio
async def test_rpc_error_envelope_discloses_no_marker_bearing_parameters() -> None:
    """Rejected request parameters must not be echoed back onto the error surface."""

    dispatcher = await _initialized({})
    responses = await dispatcher.handle_frame(
        _frame("r2", "session.list", {"private": LOOPPLANE_PATH_MARKER})
    )

    assert responses
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))


def test_fixed_public_error_catalogue_is_secondary_safe() -> None:
    """Every shipped error envelope is a secondary surface and must stay clean."""

    catalogue = (
        INTERNAL_FAILURE,
        PARSE_ERROR,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        INVALID_PARAMS,
    )
    payloads = [
        SurfacePayload(
            kind="diagnostic", text=json.dumps(error.to_jsonrpc(), ensure_ascii=False)
        )
        for error in catalogue
    ]
    assert scan_secondary_surfaces(payloads) == []


@pytest.mark.anyio
async def test_cost_projection_discloses_no_marker_bearing_host_state() -> None:
    """083: marker-bearing host failures degrade to explicit absence on the wire."""

    from methods.cost import CostMethods

    class _Summary:
        session_id = "s-1"
        principal_id = "principal-opaque"

    class _PoisonedHost:
        def list_sessions(self) -> tuple[Any, ...]:
            return (_Summary(),)

        def session_cost(self, session_id: str) -> None:
            raise RuntimeError(POISONED)

        def agent_controls(self, session_id: str) -> None:
            raise RuntimeError(POISONED)

        def monthly_spend(self, principal_id: str) -> None:
            raise RuntimeError(POISONED)

    methods = CostMethods(_PoisonedHost(), principal_id="principal-opaque")  # type: ignore[arg-type]
    dispatcher = await _initialized(methods.handlers())
    responses = await dispatcher.handle_frame(
        _frame("r-cost", "cost.get", {"session_id": "s-1"})
    )

    assert responses
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="status", text=text))
    assert responses[0]["result"]["session"] == {"status": "unavailable", "usd": None}
    assert responses[0]["result"]["monthly"] == {"status": "unavailable", "usd": None}
    assert "principal-opaque" not in text


@pytest.mark.anyio
async def test_cost_projection_clamps_marker_bearing_pricing_vocabulary() -> None:
    """083: an unexpected pricing literal is clamped, never echoed to the wire."""

    from decimal import Decimal

    from methods.cost import CostMethods

    class _Summary:
        session_id = "s-1"
        principal_id = None

    class _Budget:
        pricing = POISONED

    class _Projection:
        budget = _Budget()

    class _WeirdHost:
        def list_sessions(self) -> tuple[Any, ...]:
            return (_Summary(),)

        def session_cost(self, session_id: str) -> Decimal:
            return Decimal("1.5")

        def agent_controls(self, session_id: str) -> Any:
            return _Projection()

        def monthly_spend(self, principal_id: str) -> None:
            return None

    methods = CostMethods(_WeirdHost())  # type: ignore[arg-type]
    dispatcher = await _initialized(methods.handlers())
    responses = await dispatcher.handle_frame(
        _frame("r-cost-2", "cost.get", {"session_id": "s-1"})
    )

    assert responses
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="status", text=text))
    assert responses[0]["result"]["session"] == {"status": "unknown", "usd": "1.5"}


@pytest.mark.anyio
async def test_capability_projections_disclose_no_endpoint_credential_or_owner() -> (
    None
):
    """083 Wave 4: MCP / skill / memory projections are marker-free allowlists."""

    from methods.capability import CapabilityMethods

    class _Record:
        def __init__(self, **fields: Any) -> None:
            for key, value in fields.items():
                setattr(self, key, value)

    poisoned_mcp = _Record(
        id="mcp-1",
        name="internal",
        status="unavailable",
        tool_count=1,
        transport="http",
        url=f"https://user:{POISONED}@host/{POISONED}",
        tools=("alpha",),
        problem=POISONED,
        owner_id=POISONED,
        scope="owned",
        actions=("open",),
    )
    poisoned_skill = _Record(
        id="skill-1",
        name="notes",
        description="notes",
        source=POISONED,
        problem=POISONED,
        status="available",
        scope="owned",
        actions=("open",),
        instructions="write",
    )
    poisoned_memory = _Record(
        id="memory-1",
        name="prefs",
        kind="user",
        description="prefs",
        snippet="dark",
        problem=POISONED,
        status="available",
        scope="owned",
        actions=("open",),
        content="dark theme",
    )

    class _PoisonedHost:
        def list_managed_mcp(self, principal_id: str | None = None) -> tuple[Any, ...]:
            return (poisoned_mcp,)

        def get_managed_mcp(
            self, mcp_id: str, *, principal_id: str | None = None
        ) -> Any:
            return poisoned_mcp

        def list_managed_skills(
            self, principal_id: str | None = None
        ) -> tuple[Any, ...]:
            return (poisoned_skill,)

        def get_managed_skill(
            self, skill_id: str, *, principal_id: str | None = None
        ) -> Any:
            return poisoned_skill

        def list_managed_memory(
            self, *, principal_id: str | None = None
        ) -> tuple[Any, ...]:
            return (poisoned_memory,)

        def get_managed_memory(
            self, memory_id: str, *, principal_id: str | None = None
        ) -> Any:
            return poisoned_memory

    methods = CapabilityMethods(_PoisonedHost())  # type: ignore[arg-type]
    dispatcher = await _initialized(methods.handlers())
    for req_id, (method, params) in enumerate(
        (
            ("mcp.list", {}),
            ("mcp.get", {"mcp_id": "mcp-1"}),
            ("skill.list", {}),
            ("skill.get", {"skill_id": "skill-1"}),
            ("memory.list", {}),
            ("memory.get", {"memory_id": "memory-1"}),
        )
    ):
        responses = await dispatcher.handle_frame(
            _frame(f"r-cap-{req_id}", method, params)
        )
        assert responses, method
        text = json.dumps(responses[0], ensure_ascii=False)
        assert_secondary_surface_clean(SurfacePayload(kind="status", text=text))


@pytest.mark.anyio
async def test_capability_mutation_failure_discloses_no_marker() -> None:
    """083 Wave 4: a raising mutation answers the catalogue, not the raw error."""

    from methods.capability import CapabilityMethods

    class _BrokenHost:
        async def upsert_managed_mcp(self, **kwargs: Any) -> Any:
            raise RuntimeError(POISONED)

        def write_managed_memory(self, **kwargs: Any) -> Any:
            raise RuntimeError(POISONED)

    methods = CapabilityMethods(_BrokenHost())  # type: ignore[arg-type]
    dispatcher = await _initialized(methods.handlers())
    for req_id, (method, params) in enumerate(
        (
            (
                "mcp.upsert",
                {
                    "mutation_id": "m-1",
                    "name": "srv",
                    "transport": "http",
                    "url": "https://mcp.example",
                },
            ),
            (
                "memory.write",
                {
                    "mutation_id": "m-2",
                    "name": "prefs",
                    "kind": "user",
                    "description": "",
                    "content": "dark",
                },
            ),
        )
    ):
        responses = await dispatcher.handle_frame(
            _frame(f"r-cap-mut-{req_id}", method, params)
        )
        assert responses, method
        text = json.dumps(responses[0], ensure_ascii=False)
        assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))
        assert (
            responses[0]["error"]["data"]["messageKey"] == "desktop.error.unavailable"
        )


@pytest.mark.anyio
async def test_governance_projections_disclose_no_owner_or_problem() -> None:
    """083 Wave 5: schedule / context / model-default projections are marker-free."""

    from methods.governance import GovernanceMethods

    class _Record:
        def __init__(self, **fields: Any) -> None:
            for key, value in fields.items():
                setattr(self, key, value)

    poisoned_schedule = _Record(
        id="schedule-1",
        name="daily",
        description="daily",
        trigger="0 9 * * *",
        enabled=True,
        instruction="refresh",
        status="disabled",
        problem=POISONED,
        owner_id=POISONED,
        scope="owned",
        actions=("open",),
    )
    poisoned_context = _Record(
        id="context-1",
        name="Docs",
        description="docs",
        workspace_label="docs-repo",
        status="available",
        problem=POISONED,
        owner_id=POISONED,
        scope="owned",
        actions=("open",),
    )
    poisoned_default = _Record(
        model_id="model-x",
        label="Model X",
        status="available",
        problem=POISONED,
    )

    class _PoisonedHost:
        def list_managed_schedules(
            self, principal_id: str | None = None
        ) -> tuple[Any, ...]:
            return (poisoned_schedule,)

        def get_managed_schedule(
            self, schedule_id: str, *, principal_id: str | None = None
        ) -> Any:
            return poisoned_schedule

        def list_workspace_contexts(
            self, principal_id: str | None = None
        ) -> tuple[Any, ...]:
            return (poisoned_context,)

        def get_workspace_context(
            self, context_id: str, *, principal_id: str | None = None
        ) -> Any:
            return poisoned_context

        def model_default(
            self, principal_id: str | None = None, *, available_models: Any = None
        ) -> Any:
            return poisoned_default

        def upsert_managed_schedule(self, **kwargs: Any) -> Any:
            raise RuntimeError(POISONED)

    methods = GovernanceMethods(
        _PoisonedHost(),  # type: ignore[arg-type]
        configured_model_id="model-x",
    )
    dispatcher = await _initialized(methods.handlers())
    for req_id, (method, params) in enumerate(
        (
            ("schedule.list", {}),
            ("schedule.get", {"schedule_id": "schedule-1"}),
            ("context.list", {}),
            ("context.get", {"context_id": "context-1"}),
            ("modelDefault.get", {}),
        )
    ):
        responses = await dispatcher.handle_frame(
            _frame(f"r-gov-{req_id}", method, params)
        )
        assert responses, method
        text = json.dumps(responses[0], ensure_ascii=False)
        assert_secondary_surface_clean(SurfacePayload(kind="status", text=text))

    failed = await dispatcher.handle_frame(
        _frame(
            "r-gov-mut",
            "schedule.upsert",
            {
                "mutation_id": "m-1",
                "name": "daily",
                "description": "",
                "trigger": "0 9 * * *",
                "instruction": "refresh",
                "enabled": True,
            },
        )
    )
    assert failed
    text = json.dumps(failed[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))
    assert failed[0]["error"]["data"]["messageKey"] == "desktop.error.unavailable"


@pytest.mark.anyio
async def test_command_execute_answers_fixed_text_over_a_failing_seam() -> None:
    """083 Wave 6 (ADR 0017): a marker-bearing seam failure never reaches the wire."""

    from decimal import Decimal

    from methods.command import CommandMethods

    class _PoisonedHost:
        def list_sessions(self) -> tuple[Any, ...]:
            return ()

        def session_cost(self, session_id: str) -> Decimal | None:
            raise RuntimeError(POISONED)

        def monthly_spend(self, principal_id: str) -> Decimal | None:
            raise RuntimeError(POISONED)

        def inspect_memory(self, query: str | None = None) -> tuple[Any, ...]:
            raise RuntimeError(POISONED)

        def compact_session(self, session_id: str) -> bool:
            raise RuntimeError(POISONED)

    methods = CommandMethods(_PoisonedHost(), principal_id="principal-opaque")  # type: ignore[arg-type]
    dispatcher = await _initialized(methods.handlers())
    for req_id, text in enumerate(("/cost", "/memory", "/nonsense")):
        responses = await dispatcher.handle_frame(
            _frame(
                f"r-cmd-{req_id}",
                "command.execute",
                {"mutation_id": f"m-{req_id}", "text": text},
            )
        )
        assert responses, text
        wire = json.dumps(responses[0], ensure_ascii=False)
        assert_secondary_surface_clean(SurfacePayload(kind="status", text=wire))
        assert responses[0]["result"]["kind"] in {"ok", "unknown", "error"}


def test_backup_disclosure_is_secondary_safe() -> None:
    disclosure = json.dumps(describe_backup().to_public(), ensure_ascii=False)
    assert_secondary_surface_clean(
        SurfacePayload(kind="backup_manifest", text=disclosure)
    )


def test_archive_routes_authorized_content_without_leaking_into_metadata(
    tmp_path: Path,
) -> None:
    """Authorized conversation text survives in the entry, never in the manifest."""

    snapshot = tmp_path / "snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    conversation = "\n".join(
        (AUTHORIZED_USER_CONTENT_MARKER, AUTHORIZED_MODEL_CONTENT_MARKER)
    )
    # Write bytes, not text: universal newlines would rewrite the separator and
    # make the losslessness assertion below measure the fixture, not the product.
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(
        conversation.encode("utf-8")
    )
    destination = tmp_path / "portable.zip"

    manifest = create_portable_archive(
        destination,
        profile_portable={
            "schema_version": 1,
            "profile_id": "profile-opaque",
            "principal_id": "principal-opaque",
            "projects": [{"id": "project", "label": "Work", "session_ids": ["s"]}],
            "preferences": {"theme": "dark", "composer_draft": LOOPPLANE_SECRET_MARKER},
            "workspace_references": [
                {"id": "workspace", "label": "Docs", "availability": "available"}
            ],
            "credentials": {"token": LOOPPLANE_SECRET_MARKER},
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="manifest", text=manifest_text))
    # Authorized content belongs to the entry, not to entry metadata.
    assert AUTHORIZED_USER_CONTENT_MARKER not in manifest_text

    revalidated = json.dumps(validate_archive(destination), ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="manifest", text=revalidated))

    with zipfile.ZipFile(destination, "r") as archive:
        exported_profile = archive.read("profile/profile.json").decode("utf-8")
        restored = archive.read("sessions/checkpoints.sqlite3").decode("utf-8")

    # The unsent draft and the credential are excluded, so the marker cannot ride
    # the exported profile either.
    assert_secondary_surface_clean(
        SurfacePayload(kind="manifest", text=exported_profile)
    )

    content = SurfacePayload(kind="conversation", text=restored)
    assert_content_surface_may_retain(content, AUTHORIZED_USER_CONTENT_MARKER)
    assert_content_surface_may_retain(content, AUTHORIZED_MODEL_CONTENT_MARKER)
    assert restored == conversation, "authorized content must survive losslessly"
