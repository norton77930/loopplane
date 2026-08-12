"""Session/project RPC methods (078 T042 subset)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from dispatcher import Dispatcher  # noqa: E402
from methods.projects import ProjectMethods  # noqa: E402
from methods.sessions import SessionMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import PROTOCOL_NAME, PROTOCOL_VERSION  # noqa: E402

pytestmark = pytest.mark.anyio


def _host(tmp_path: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store",
            ),
        ),
        working_scope=tmp_path,
    )


async def _init(d: Dispatcher) -> None:
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocol": PROTOCOL_NAME, "version": PROTOCOL_VERSION},
            }
        )
    )


async def test_project_crud_via_rpc(tmp_path: Path) -> None:
    state = ProfileState.open(tmp_path / "profile")
    lease = ProfileMutationLease()
    d = Dispatcher(methods=ProjectMethods(state, lease).handlers())
    await _init(d)
    created = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "project.create",
                "params": {"mutation_id": "m1", "label": "Work"},
            }
        )
    )
    assert "result" in created[0]
    project_id = created[0]["result"]["project"]["id"]
    listed = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "project.list", "params": {}})
    )
    assert len(listed[0]["result"]["projects"]) == 1
    await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "project.remove",
                "params": {"mutation_id": "m2", "project_id": project_id},
            }
        )
    )
    listed2 = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "project.list", "params": {}})
    )
    assert listed2[0]["result"]["projects"] == []


async def test_session_list_and_star(tmp_path: Path) -> None:
    host = _host(tmp_path)
    lease = ProfileMutationLease()
    # Create a durable session
    from tests.integration.conftest import EventCollector  # type: ignore

    sink = EventCollector()
    async with host.session(sink) as session:
        await session.submit("hello")
        sid = session.session_id
        _ = session.outcome()

    d = Dispatcher(methods=SessionMethods(host, lease, principal_id=None).handlers())
    await _init(d)
    listed = await d.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "session.list", "params": {}})
    )
    assert any(s["session_id"] == sid for s in listed[0]["result"]["sessions"])
    starred = await d.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session.setStarred",
                "params": {
                    "mutation_id": "m1",
                    "session_id": sid,
                    "starred": True,
                },
            }
        )
    )
    assert starred[0]["result"]["starred"] is True


async def test_profile_principal_delete_removes_legacy_none_principal_session(
    tmp_path: Path,
) -> None:
    """A legacy visible session must not report deletion while remaining durable."""

    host = _host(tmp_path)
    from tests.integration.conftest import EventCollector  # type: ignore

    sink = EventCollector()
    async with host.session(sink) as session:
        await session.submit("legacy")
        session_id = session.session_id
        _ = session.outcome()

    dispatcher = Dispatcher(
        methods=SessionMethods(
            host,
            ProfileMutationLease(),
            principal_id="profile-principal",
        ).handlers()
    )
    await _init(dispatcher)
    deleted = await dispatcher.handle_frame(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "session.delete",
                "params": {
                    "mutation_id": "delete-legacy",
                    "session_id": session_id,
                    "confirmation": True,
                },
            }
        )
    )
    assert deleted[0]["result"] == {"deleted": True, "session_id": session_id}

    listed = await dispatcher.handle_frame(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "session.list", "params": {}})
    )
    assert session_id not in {
        item["session_id"] for item in listed[0]["result"]["sessions"]
    }
