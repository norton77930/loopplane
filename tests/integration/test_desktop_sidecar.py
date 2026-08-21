"""The desktop sidecar bridge streams a run over stdio (T002; FR-001/FR-002, SC-001).

The bridge lives under ``apps/desktop/sidecar/`` (the desktop app, not the
``loopplane`` package); it is loaded by file path so it is neither in the wheel nor a
new package.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.cli_helpers import scripted_host

pytestmark = pytest.mark.anyio

_BRIDGE_PATH = (
    Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar" / "bridge.py"
)


def _load_bridge() -> ModuleType:
    spec = importlib.util.spec_from_file_location("desktop_bridge", _BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge()


async def test_collect_events_streams_a_run() -> None:
    host = scripted_host("hi there")
    lines = await bridge.collect_events(host, "hello")
    assert any('"assistant-output-increment"' in line for line in lines)
    assert any('"hi there"' in line for line in lines)
    assert "outcome" in lines[-1]  # the terminal outcome is the final line


async def test_serve_drives_a_run_and_writes_an_outcome() -> None:
    host = scripted_host("done")
    pending: list[str | None] = ['{"op": "run", "prompt": "hello"}', None]

    async def read_line() -> str | None:
        return pending.pop(0) if pending else None

    out: list[str] = []
    await bridge.serve(host, read_line, out.append)
    assert any('"assistant-output-increment"' in line for line in out)
    assert any('"op": "outcome"' in line for line in out)


async def test_serve_reports_a_malformed_request() -> None:
    host = scripted_host("x")
    pending: list[str | None] = ["not json", None]

    async def read_line() -> str | None:
        return pending.pop(0) if pending else None

    out: list[str] = []
    await bridge.serve(host, read_line, out.append)
    assert any('"op": "error"' in line for line in out)


def test_select_desktop_model_is_scripted_only_for_packaged_smoke() -> None:
    smoke = bridge.select_desktop_model({"LOOPPLANE_PACKAGED_SMOKE_SCENARIO": "happy"})
    normal = bridge.select_desktop_model({})

    assert type(smoke).__name__ == "ScriptedModel"
    assert type(normal).__name__ == "DemoModel"


async def test_normal_desktop_model_supports_consecutive_turns() -> None:
    from loopplane.model import ModelRequest

    model = bridge.select_desktop_model({})
    first = [
        increment async for increment in model.stream_turn(ModelRequest(context=[]))
    ]
    second = [
        increment async for increment in model.stream_turn(ModelRequest(context=[]))
    ]

    assert first
    assert second


def test_entrypoint_negotiates_before_profile_bootstrap(tmp_path: Path) -> None:
    profile_file = tmp_path / "profile-file"
    profile_file.write_text("not a directory", encoding="utf-8")
    entrypoint = _BRIDGE_PATH.with_name("__main__.py")
    request = {
        "jsonrpc": "2.0",
        "id": "initialize-1",
        "method": "initialize",
        "params": {
            "protocol": {
                "name": "loopplane.desktop.stdio",
                "major": 1,
                "minor": 0,
            },
            "runtime_event_schema": 1,
            "client": {"name": "test-client", "version": "0"},
            "requested_capabilities": [
                "sessions",
                "interaction",
                "projects",
                "inspection",
                "workspace",
                "backup",
            ],
        },
    }
    env = os.environ.copy()
    env["LOOPPLANE_PROFILE_ROOT"] = str(profile_file)
    env["LOOPPLANE_PACKAGED_SMOKE_SCENARIO"] = "happy"
    for name in ("LOOPPLANE_STAGE_B_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        env.pop(name, None)

    completed = subprocess.run(
        [sys.executable, str(entrypoint)],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 2
    response = json.loads(completed.stdout.splitlines()[0])
    assert response["id"] == "initialize-1"
    assert response["result"]["protocol"] == {
        "name": "loopplane.desktop.stdio",
        "major": 1,
        "minor": 0,
    }
    assert response["result"]["methods"] == [
        "agentControls.get",
        "audit.list",
        "backup.create",
        "backup.describe",
        "capabilities.invokeAction",
        "capabilities.list",
        "command.execute",
        "context.bind",
        "context.delete",
        "context.get",
        "context.list",
        "context.upsert",
        "cost.get",
        "initialize",
        "inspection.get",
        "interaction.answerApproval",
        "interaction.answerQuestion",
        "interaction.cancel",
        "interaction.submit",
        "mcp.delete",
        "mcp.get",
        "mcp.list",
        "mcp.reconnect",
        "mcp.upsert",
        "memory.delete",
        "memory.get",
        "memory.list",
        "memory.write",
        "modelDefault.clear",
        "modelDefault.get",
        "modelDefault.set",
        "project.assignSession",
        "project.create",
        "project.list",
        "project.remove",
        "project.rename",
        "restore.cancel",
        "restore.commit",
        "restore.validate",
        "schedule.delete",
        "schedule.disable",
        "schedule.enable",
        "schedule.get",
        "schedule.list",
        "schedule.runNow",
        "schedule.upsert",
        "session.createInteractive",
        "session.delete",
        "session.fork",
        "session.history",
        "session.list",
        "session.releaseInteractive",
        "session.rename",
        "session.resumeInteractive",
        "session.setStarred",
        "skill.delete",
        "skill.get",
        "skill.import",
        "skill.list",
        "skill.write",
        "system.shutdown",
        "system.status",
        "workspace.bind",
        "workspace.list",
        "workspace.relink",
        "workspace.remove",
        "workspace.revalidate",
    ]


# --- US2 T036: session / project / workspace over composed RPC dispatcher ---


def _initialize_params() -> dict:
    return {
        "protocol": {
            "name": "loopplane.desktop.stdio",
            "major": 1,
            "minor": 0,
        },
        "runtime_event_schema": 1,
        "client": {"name": "test-client", "version": "0"},
        "requested_capabilities": [],
    }


async def _rpc_call(dispatcher: object, req_id: int, method: str, params: dict) -> dict:
    import json

    frames = await dispatcher.handle_frame(  # type: ignore[attr-defined]
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": f"request-{req_id}",
                "method": method,
                "params": params,
            }
        )
    )
    assert frames, f"no response for {method}"
    return frames[0]


async def test_rpc_session_list_star_and_project_workspace(tmp_path: Path) -> None:
    """Host-backed session list/star + profile project/workspace methods (T036)."""

    import json
    import sys

    from loopplane.host import (
        DesktopStorageAuthorityFactory,
        LoopPlaneHost,
        RuntimeConfig,
        StorageConfig,
    )
    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

    sidecar = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
    sys.path.insert(0, str(sidecar))

    from profile import ProfileState

    from durability import initialize_runtime_storage
    from mutation_lease import ProfileMutationLease

    profile_root = tmp_path / "profile"
    state = ProfileState.open(profile_root)
    storage_root = initialize_runtime_storage(state.root, "g0")
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                authority=DesktopStorageAuthorityFactory(state.root),
                checkpoint_backend="sqlite",
                root=storage_root,
            ),
        ),
        working_scope=tmp_path,
    )
    lease = ProfileMutationLease()

    dispatcher = bridge.build_rpc_dispatcher(
        host,
        working_scope=tmp_path,
        profile_state=state,
        mutation_lease=lease,
        principal_id=state.principal_id,
    )

    # initialize
    init = await _rpc_call(
        dispatcher,
        0,
        "initialize",
        _initialize_params(),
    )
    assert "result" in init
    methods = init["result"].get("methods") or []
    assert methods == [
        "agentControls.get",
        "audit.list",
        "backup.create",
        "backup.describe",
        "capabilities.invokeAction",
        "capabilities.list",
        "command.execute",
        "context.bind",
        "context.delete",
        "context.get",
        "context.list",
        "context.upsert",
        "cost.get",
        "initialize",
        "inspection.get",
        "interaction.answerApproval",
        "interaction.answerQuestion",
        "interaction.cancel",
        "interaction.submit",
        "mcp.delete",
        "mcp.get",
        "mcp.list",
        "mcp.reconnect",
        "mcp.upsert",
        "memory.delete",
        "memory.get",
        "memory.list",
        "memory.write",
        "modelDefault.clear",
        "modelDefault.get",
        "modelDefault.set",
        "project.assignSession",
        "project.create",
        "project.list",
        "project.remove",
        "project.rename",
        "restore.cancel",
        "restore.commit",
        "restore.validate",
        "schedule.delete",
        "schedule.disable",
        "schedule.enable",
        "schedule.get",
        "schedule.list",
        "schedule.runNow",
        "schedule.upsert",
        "session.createInteractive",
        "session.delete",
        "session.fork",
        "session.history",
        "session.list",
        "session.releaseInteractive",
        "session.rename",
        "session.resumeInteractive",
        "session.setStarred",
        "skill.delete",
        "skill.get",
        "skill.import",
        "skill.list",
        "skill.write",
        "system.shutdown",
        "system.status",
        "workspace.bind",
        "workspace.list",
        "workspace.relink",
        "workspace.remove",
        "workspace.revalidate",
    ]

    # create a durable session via Host interactive API
    from tests.integration.conftest import EventCollector

    sink = EventCollector()
    async with host.session(sink) as session:
        await session.submit("hello")
        sid = session.session_id
        _ = session.outcome()

    listed = await _rpc_call(dispatcher, 1, "session.list", {})
    assert any(s["session_id"] == sid for s in listed["result"]["sessions"])

    starred = await _rpc_call(
        dispatcher,
        2,
        "session.setStarred",
        {"mutation_id": "m-star", "session_id": sid, "starred": True},
    )
    assert starred["result"]["starred"] is True

    hist = await _rpc_call(dispatcher, 3, "session.history", {"session_id": sid})
    assert hist["result"]["session_id"] == sid

    proj = await _rpc_call(
        dispatcher,
        4,
        "project.create",
        {"mutation_id": "m-p", "label": "Alpha"},
    )
    project_id = proj["result"]["project"]["id"]
    await _rpc_call(
        dispatcher,
        5,
        "project.assignSession",
        {
            "mutation_id": "m-a",
            "project_id": project_id,
            "session_id": sid,
        },
    )
    pl = await _rpc_call(dispatcher, 6, "project.list", {})
    assert pl["result"]["projects"][0]["session_ids"] == [sid]

    # workspace bind with trusted path; projection has no absolute path
    ws = tmp_path / "workspace"
    ws.mkdir()
    bound = await _rpc_call(
        dispatcher,
        7,
        "workspace.bind",
        {
            "mutation_id": "m-w",
            "path": str(ws),
            "label": "Docs",
        },
    )
    ref = bound["result"]["workspace"]
    assert ref["label"] == "Docs"
    assert str(ws) not in json.dumps(bound)
    wlist = await _rpc_call(dispatcher, 8, "workspace.list", {})
    assert len(wlist["result"]["workspaces"]) == 1
    assert str(ws) not in json.dumps(wlist)

    # remove project does not delete session
    await _rpc_call(
        dispatcher,
        9,
        "project.remove",
        {"mutation_id": "m-rm", "project_id": project_id},
    )
    listed2 = await _rpc_call(dispatcher, 10, "session.list", {})
    assert any(s["session_id"] == sid for s in listed2["result"]["sessions"])

    # 083: cost projection answers with explicit absence on an unconfigured host
    cost = await _rpc_call(dispatcher, 11, "cost.get", {"session_id": sid})
    assert cost["result"]["session"]["status"] in {
        "priced",
        "partially_unpriced",
        "unpriced",
        "unknown",
        "unavailable",
    }
    session_usd = cost["result"]["session"]["usd"]
    assert session_usd is None or isinstance(session_usd, str)
    assert cost["result"]["monthly"] == {"status": "unavailable", "usd": None}
    caps = await _rpc_call(dispatcher, 12, "capabilities.list", {})
    assert any(
        c["id"] == "cost" and c["available"] is False
        for c in caps["result"]["capabilities"]
    )

    # 083 Wave 4: capability management binds through the composed dispatcher.
    mcp = await _rpc_call(dispatcher, 13, "mcp.list", {})
    assert mcp["result"]["items"] == []
    skills = await _rpc_call(dispatcher, 14, "skill.list", {})
    assert skills["result"]["items"] == []
    await host.aclose()


async def test_rpc_resume_rejects_foreign_principal_session(tmp_path: Path) -> None:
    """Desktop resume cannot attach a known session owned by another principal."""

    import sys

    from loopplane.host import (
        DesktopStorageAuthorityFactory,
        LoopPlaneHost,
        RuntimeConfig,
        StorageConfig,
    )
    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
    from tests.integration.conftest import EventCollector

    sidecar = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
    sys.path.insert(0, str(sidecar))

    from profile import ProfileState

    from durability import initialize_runtime_storage

    state = ProfileState.open(tmp_path / "profile")
    storage_root = initialize_runtime_storage(state.root, "g0")
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="foreign")])],
                context_capacity=100_000,
            ),
            storage=StorageConfig(
                authority=DesktopStorageAuthorityFactory(state.root),
                checkpoint_backend="sqlite",
                root=storage_root,
            ),
        ),
        working_scope=tmp_path,
    )
    sink = EventCollector()
    async with host.session(sink, principal_id="foreign-principal") as session:
        await session.submit("foreign history")
        foreign_session_id = session.session_id

    dispatcher = bridge.build_rpc_dispatcher(
        host,
        working_scope=tmp_path,
        profile_state=state,
        principal_id=state.principal_id,
    )
    await _rpc_call(
        dispatcher,
        0,
        "initialize",
        _initialize_params(),
    )
    resumed = await _rpc_call(
        dispatcher,
        1,
        "session.resumeInteractive",
        {
            "mutation_id": "resume-foreign",
            "session_id": foreign_session_id,
            "pane_id": "pane-1",
        },
    )

    assert resumed["error"]["data"]["category"] == "not_found"
    await host.aclose()


async def test_rpc_audit_list_is_principal_scoped_opaque_and_metadata_only(
    tmp_path: Path,
) -> None:
    """The sidecar owns cursor validation and emits only the audit allowlist."""

    import json
    import sys

    from loopplane.host import (
        DesktopStorageAuthorityFactory,
        LoopPlaneHost,
        RuntimeConfig,
        StorageConfig,
    )
    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

    sidecar = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
    sys.path.insert(0, str(sidecar))
    from profile import ProfileState

    from durability import initialize_runtime_storage
    from mutation_lease import ProfileMutationLease

    profile = ProfileState.open(tmp_path / "profile")
    storage_root = initialize_runtime_storage(profile.root, "g0")
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="first")]),
            ScriptedTurn(increments=[TextIncrement(text="second")]),
            ScriptedTurn(increments=[TextIncrement(text="other")]),
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                authority=DesktopStorageAuthorityFactory(profile.root),
                checkpoint_backend="sqlite",
                root=storage_root,
            ),
        ),
        working_scope=tmp_path,
    )

    async def sink(_event: object) -> None:
        return None

    async with host.session(sink, principal_id=profile.principal_id) as session:
        await session.submit("sidecar-private-prompt-one")
        await session.submit("sidecar-private-prompt-two")
        session_id = session.session_id
    async with host.session(sink, principal_id=profile.principal_id) as other_session:
        await other_session.submit("sidecar-private-other-session")
        other_session_id = other_session.session_id

    dispatcher = bridge.build_rpc_dispatcher(
        host,
        working_scope=tmp_path,
        profile_state=profile,
        mutation_lease=ProfileMutationLease(),
        principal_id=profile.principal_id,
    )
    await _rpc_call(
        dispatcher,
        20,
        "initialize",
        _initialize_params(),
    )
    first = await _rpc_call(
        dispatcher, 21, "audit.list", {"session_id": session_id, "limit": 1}
    )
    result = first["result"]
    assert set(result) == {"session_id", "entries", "next_cursor"}
    assert len(result["entries"]) == 1
    assert set(result["entries"][0]) == {
        "audit_id",
        "session_id",
        "turn_ordinal",
        "checkpoint_sequence",
        "recorded_at",
        "state",
        "termination_reason",
        "turns_taken",
    }
    assert isinstance(result["next_cursor"], str)
    assert "sidecar-private-prompt" not in json.dumps(result)
    assert profile.principal_id not in json.dumps(result)

    second = await _rpc_call(
        dispatcher,
        22,
        "audit.list",
        {
            "session_id": session_id,
            "cursor": result["next_cursor"],
            "limit": 1,
        },
    )
    assert (
        second["result"]["entries"][0]["audit_id"] != result["entries"][0]["audit_id"]
    )
    assert second["result"]["next_cursor"] is None

    invalid = await _rpc_call(
        dispatcher,
        23,
        "audit.list",
        {"session_id": session_id, "cursor": "audit_invalid", "limit": 1},
    )
    assert invalid["error"]["code"] == -32602
    cross_session = await _rpc_call(
        dispatcher,
        24,
        "audit.list",
        {
            "session_id": other_session_id,
            "cursor": result["next_cursor"],
            "limit": 1,
        },
    )
    assert cross_session["error"]["code"] == -32602

    foreign = bridge.build_rpc_dispatcher(
        host,
        working_scope=tmp_path,
        profile_state=profile,
        mutation_lease=ProfileMutationLease(),
        principal_id="different-principal",
    )
    await _rpc_call(
        foreign,
        24,
        "initialize",
        _initialize_params(),
    )
    cross_principal = await _rpc_call(
        foreign, 25, "audit.list", {"session_id": session_id, "limit": 1}
    )
    assert cross_principal["error"]["code"] == -32002
    await host.aclose()
