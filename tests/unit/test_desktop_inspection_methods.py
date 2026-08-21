"""Host-only inspection/agent/capabilities methods (078 T060/T064)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from methods.inspection import InspectionMethods  # noqa: E402
from protocol import RpcError  # noqa: E402

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


async def test_inspection_get_is_public_safe(tmp_path: Path) -> None:
    methods = InspectionMethods(_host(tmp_path))
    result = await methods.inspection_get({})
    assert result["unavailable"] is False
    assert "tools" in result
    blob = str(result)
    assert "password" not in blob.lower()
    assert "secret" not in blob.lower()


async def test_capabilities_list_and_allowlisted_invoke(tmp_path: Path) -> None:
    methods = InspectionMethods(_host(tmp_path))
    listed = await methods.capabilities_list({})
    assert any(c["id"] == "memory" for c in listed["capabilities"])
    refreshed = await methods.capabilities_invoke(
        {
            "mutation_id": "capability-refresh",
            "capability_id": "memory",
            "action": "refresh",
        }
    )
    assert "capabilities" in refreshed
    with pytest.raises(RpcError) as exc:
        await methods.capabilities_invoke(
            {
                "mutation_id": "capability-unavailable",
                "capability_id": "memory",
                "action": "drop_db",
            }
        )
    assert exc.value.category == "unavailable"


async def test_agent_controls_requires_session_id(tmp_path: Path) -> None:
    methods = InspectionMethods(_host(tmp_path))
    with pytest.raises(RpcError):
        await methods.agent_controls_get({})
