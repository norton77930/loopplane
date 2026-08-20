"""Public safety of the terminal's output, local and remote (079 T065, FR-009,
FR-024, SC-010).

Every marker here is synthetic (`tests/helpers/public_safety.py`) — no realistic
private path, address, or credential is written into a fixture, because a fixture
that looks real is itself the leak the scan exists to catch. Marker assertions
stay on single-line probes: a payload rendered through `str()` escapes newlines,
which would let a multi-line marker pass by accident.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from loopplane.cli import chat_loop
from loopplane.cli.remote import RemoteEndpoint, remote_loop
from loopplane.context import RunContext
from loopplane.host import LoopPlaneHost, RuntimeConfig, ToolSpec
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)
from tests.helpers.public_safety import (
    LOOPPLANE_PATH_MARKER,
    LOOPPLANE_RULE_MARKER,
    LOOPPLANE_SECRET_MARKER,
    SurfacePayload,
    assert_secondary_surface_clean,
)

pytestmark = pytest.mark.anyio

# The raw-error marker is multi-line; this is its single-line probe.
_STACK_PROBE = "lp-synth-internal-stack"


LEAKY_DESCRIPTOR = ToolDescriptor(
    name="leaky",
    description="A tool whose failure carries private detail.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)


async def leaky_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    raise RuntimeError(
        f"failed reading {LOOPPLANE_PATH_MARKER} under {LOOPPLANE_RULE_MARKER} "
        f"({_STACK_PROBE})"
    )


LEAKY_TOOL = ToolSpec(descriptor=LEAKY_DESCRIPTOR, handler=leaky_handler)


def _leaky_host() -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[
                    ScriptedTurn(
                        increments=[
                            ToolCallRequest(call_id="c1", tool_name="leaky", input={})
                        ],
                        stop_reason="tool-use",
                    ),
                    ScriptedTurn(increments=[TextIncrement(text="moving on")]),
                ],
                context_capacity=100_000,
            ),
            tools=(LEAKY_TOOL,),
        )
    )


async def test_a_failing_tool_leaks_nothing_into_the_terminal() -> None:
    out = io.StringIO()
    await chat_loop(_leaky_host(), ["do the thing", "quit"], out)
    rendered = out.getvalue()
    assert "[tool leaky]" in rendered  # the failure IS reported...
    assert "failure" in rendered
    assert_secondary_surface_clean(SurfacePayload(kind="log", text=rendered))
    assert _STACK_PROBE not in rendered  # ...but never with its private detail


async def test_the_remote_credential_never_reaches_the_output() -> None:
    pytest.importorskip("httpx")
    import httpx

    def refuse(request: httpx.Request) -> httpx.Response:
        # Even a server that echoes the credential back cannot make the terminal
        # print it: the client renders fixed public-safe text, never a response.
        return httpx.Response(
            401, json={"detail": f"bad credential {LOOPPLANE_SECRET_MARKER}"}
        )

    out = io.StringIO()
    code = await remote_loop(
        RemoteEndpoint(base_url="http://remote.invalid", token=LOOPPLANE_SECRET_MARKER),
        ["hello"],
        out,
        transport=httpx.MockTransport(refuse),
    )
    assert code == 1
    rendered = out.getvalue()
    assert LOOPPLANE_SECRET_MARKER not in rendered
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=rendered))


async def test_a_transport_failure_carrying_private_detail_is_normalized() -> None:
    pytest.importorskip("httpx")
    import httpx

    def explode(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"cannot reach {LOOPPLANE_PATH_MARKER} ({_STACK_PROBE})"
        )

    out = io.StringIO()
    code = await remote_loop(
        RemoteEndpoint(base_url="http://remote.invalid", token=LOOPPLANE_SECRET_MARKER),
        ["hello"],
        out,
        transport=httpx.MockTransport(explode),
    )
    assert code == 1
    rendered = out.getvalue()
    assert "could not reach the server" in rendered
    assert _STACK_PROBE not in rendered
    assert_secondary_surface_clean(SurfacePayload(kind="diagnostic", text=rendered))


async def test_the_usage_error_does_not_echo_what_was_supplied(
    tmp_path: Path,
) -> None:
    import anyio

    from loopplane.cli import dispatch

    out = io.StringIO()

    # `dispatch` owns its own event loop, so it runs in a worker thread here.
    def run() -> int:
        # A poisoned token with no --url: the usage error must name neither.
        return dispatch(["remote", "--token", LOOPPLANE_SECRET_MARKER], out)

    code = await anyio.to_thread.run_sync(run)
    assert code == 2
    assert LOOPPLANE_SECRET_MARKER not in out.getvalue()
