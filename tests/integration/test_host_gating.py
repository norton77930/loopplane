"""US2: gating equality — with all optional subsystems off, a run through the
host interface produces the same event sequence as a bare Phase-1 controller
(spec US2; SC-003, FR-012/043).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
)

from .conftest import ECHO_DESCRIPTOR, ECHO_TOOL, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


def _script() -> list[ScriptedTurn]:
    return [
        ScriptedTurn(
            increments=[
                TextIncrement(text="thinking"),
                ToolCallRequest(call_id="c1", tool_name="echo", input={"text": "x"}),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


async def test_gated_run_matches_bare_controller(tmp_path: Path) -> None:
    bare_sink = EventCollector()
    bare_gateway = ToolGateway()
    bare_gateway.register(ECHO_DESCRIPTOR, echo_handler)
    bare = RuntimeController(
        model=ScriptedModel(script=_script(), context_capacity=100_000),
        gateway=bare_gateway,
        event_sink=bare_sink,
    )
    bare_session = bare.create_session(working_scope=tmp_path)
    await bare.drive(bare_session, [TextBlock(text="go")])

    host_sink = EventCollector()
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(script=_script(), context_capacity=100_000),
            tools=(ECHO_TOOL,),
        ),
        working_scope=tmp_path,
    )
    await host.run([TextBlock(text="go")], host_sink)

    assert host_sink.types == bare_sink.types
