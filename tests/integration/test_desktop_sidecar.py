"""The desktop sidecar bridge streams a run over stdio (T002; FR-001/FR-002, SC-001).

The bridge lives under ``apps/desktop/sidecar/`` (the desktop app, not the
``loopplane`` package); it is loaded by file path so it is neither in the wheel nor a
new package.
"""

from __future__ import annotations

import importlib.util
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


# --- US2 T036: session / project / workspace over composed RPC dispatcher ---


async def _rpc_call(dispatcher: object, req_id: int, method: str, params: dict) -> dict:
    import json

    frames = await dispatcher.handle_frame(  # type: ignore[attr-defined]
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
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
        {"protocol": "loopplane.desktop.stdio", "version": 1},
    )
    assert "result" in init
    methods = init["result"].get("methods") or []
    for name in (
        "session.list",
        "session.setStarred",
        "project.create",
        "workspace.bind",
        "workspace.list",
    ):
        assert name in methods

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
        {"protocol": "loopplane.desktop.stdio", "version": 1},
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
        {"protocol": "loopplane.desktop.stdio", "version": 1},
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
        {"protocol": "loopplane.desktop.stdio", "version": 1},
    )
    cross_principal = await _rpc_call(
        foreign, 25, "audit.list", {"session_id": session_id, "limit": 1}
    )
    assert cross_principal["error"]["code"] == -32002
    await host.aclose()
