"""US2 acceptance 2.3 and 2.4 with a local test MCP server fixture
(FR-040–FR-045): external tools pass the same Gateway pipeline as internal
tools, and one failing server never takes the others down.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.adapters.mcp import MCPServerConfig, MCPToolAdapter, merge_layers
from loopplane.approval import HumanApproval, PermissionRule
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.model import TextBlock, ToolCallRequest

from .conftest import ECHO_DESCRIPTOR, echo_handler

pytestmark = pytest.mark.anyio

FIXTURE_SERVER = Path(__file__).resolve().parents[1] / "fixtures" / "mcp_echo_server.py"


def _good_server(name: str = "ext") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport="stdio",
        command=sys.executable,
        args=(str(FIXTURE_SERVER),),
    )


def _broken_server(name: str = "broken") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport="stdio",
        command=sys.executable,
        args=("-c", "import sys; sys.exit(1)"),
    )


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


async def _execute(gateway: ToolGateway, call: ToolCallRequest, tmp_path: Path):
    results = await gateway.execute_batch(
        [call],
        parallel=False,
        context=RunContext(session_id="session-1", working_scope=tmp_path),
        emitter=EventEmitter(
            session_id="session-1", sequencer=EventSequencer(), sink=_Collector()
        ),
    )
    return results[0]


def test_layered_config_overrides_by_name_and_isolates_malformed_entries() -> None:
    broad = {
        "ext": {"transport": "stdio", "command": "old-command"},
        "other": {"transport": "stdio", "command": "other-command"},
    }
    specific = {
        "ext": {"transport": "stdio", "command": "new-command"},
        "bad": {"transport": "stdio"},  # malformed: stdio without a command
    }

    configs, problems = merge_layers([broad, specific])

    by_name = {config.name: config for config in configs}
    assert by_name["ext"].command == "new-command"
    assert "other" in by_name
    assert "bad" not in by_name
    assert len(problems) == 1 and "bad" in problems[0]


async def test_external_tool_passes_the_same_pipeline_as_internal(
    tmp_path: Path,
) -> None:
    """Acceptance 2.3 + FR-042/FR-045: source-qualified name, same permission
    check, same normalized result shape.
    """
    async with MCPToolAdapter([_good_server()]) as adapter:
        assert adapter.connection_failures == {}
        gateway = ToolGateway(
            decide=HumanApproval(
                rules=[
                    PermissionRule(matcher="echo", effect="allow", scope="project"),
                    PermissionRule(
                        matcher="ext:mcp_echo", effect="allow", scope="project"
                    ),
                    PermissionRule(
                        matcher="ext:mcp_fail", effect="deny", scope="project"
                    ),
                ]
            )
        )
        gateway.register(ECHO_DESCRIPTOR, echo_handler)
        gateway.register_adapter(adapter)

        names = [descriptor.name for descriptor in gateway.descriptors()]
        assert "ext:mcp_echo" in names and "ext:mcp_fail" in names

        success = await _execute(
            gateway,
            ToolCallRequest(
                call_id="c1", tool_name="ext:mcp_echo", input={"text": "ping"}
            ),
            tmp_path,
        )
        assert success.outcome == "success"
        assert any(
            isinstance(block, TextBlock) and "mcp says: ping" in block.text
            for block in success.outputs
        )

        denied = await _execute(
            gateway,
            ToolCallRequest(
                call_id="c2", tool_name="ext:mcp_fail", input={"text": "x"}
            ),
            tmp_path,
        )
        assert denied.outcome == "failure"
        assert denied.error is not None
        assert denied.error.category == "policy-denial"

        internal = await _execute(
            gateway,
            ToolCallRequest(call_id="c3", tool_name="echo", input={"text": "pong"}),
            tmp_path,
        )
        assert internal.outcome == "success"
        # Same normalized result shape for both sources.
        assert type(internal) is type(success)


async def test_undeclared_parameters_are_rejected_for_external_tools(
    tmp_path: Path,
) -> None:
    async with MCPToolAdapter([_good_server()]) as adapter:
        gateway = ToolGateway()
        gateway.register_adapter(adapter)

        result = await _execute(
            gateway,
            ToolCallRequest(
                call_id="c1",
                tool_name="ext:mcp_echo",
                input={"text": "hi", "sneaky": 1},
            ),
            tmp_path,
        )

        assert result.outcome == "failure"
        assert result.error is not None
        assert result.error.category == "validation"


async def test_server_side_tool_error_is_a_normalized_failure(tmp_path: Path) -> None:
    async with MCPToolAdapter([_good_server()]) as adapter:
        gateway = ToolGateway()
        gateway.register_adapter(adapter)

        result = await _execute(
            gateway,
            ToolCallRequest(
                call_id="c1", tool_name="ext:mcp_fail", input={"text": "x"}
            ),
            tmp_path,
        )

        assert result.outcome == "failure"
        assert result.error is not None
        assert result.error.category == "execution"


async def test_one_failing_server_leaves_the_healthy_one_available(
    tmp_path: Path,
) -> None:
    """Acceptance 2.4 + FR-043: per-server failure isolation."""
    async with MCPToolAdapter([_broken_server(), _good_server()]) as adapter:
        assert set(adapter.connection_failures) == {"broken"}

        gateway = ToolGateway()
        gateway.register(ECHO_DESCRIPTOR, echo_handler)
        gateway.register_adapter(adapter)

        names = [descriptor.name for descriptor in gateway.descriptors()]
        assert "ext:mcp_echo" in names
        assert all(not name.startswith("broken:") for name in names)

        result = await _execute(
            gateway,
            ToolCallRequest(
                call_id="c1", tool_name="ext:mcp_echo", input={"text": "alive"}
            ),
            tmp_path,
        )
        assert result.outcome == "success"
