"""Create/resume validates workspace before Host session (078 T046)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileState  # noqa: E402

from interaction import InteractionLease  # noqa: E402
from methods.interaction import InteractionMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402
from workspace import WorkspaceStore  # noqa: E402

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


async def test_create_interactive_rejects_relink_required_workspace(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    state = ProfileState.open(profile)
    store = WorkspaceStore(state)
    ws = tmp_path / "ws"
    ws.mkdir()
    ref = store.bind(ws, label="Docs")
    store.mark_relink_required(ref["id"])

    host = _host(tmp_path)
    methods = InteractionMethods(
        host,
        InteractionLease(),
        working_scope=tmp_path,
        workspace_store=store,
        mutation_lease=ProfileMutationLease(),
    )
    with pytest.raises(RpcError) as exc:
        await methods.create_interactive(
            {
                "mutation_id": "m1",
                "workspace_id": ref["id"],
            }
        )
    assert exc.value.category == "workspace_relink_required"


async def test_create_interactive_uses_validated_workspace_scope(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    state = ProfileState.open(profile)
    store = WorkspaceStore(state)
    ws = tmp_path / "ws"
    ws.mkdir()
    ref = store.bind(ws, label="Docs")

    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(
        host,
        lease,
        working_scope=tmp_path,
        workspace_store=store,
        mutation_lease=ProfileMutationLease(),
    )
    result = await methods.create_interactive(
        {"mutation_id": "m1", "workspace_id": ref["id"]}
    )
    assert "subscription_id" in result
    assert "session_id" in result
    await lease.shutdown()
