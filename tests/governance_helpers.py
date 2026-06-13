"""Deterministic, public-safe test helpers for the governance layer (009).

Scripted tool calls / descriptors and a ``decide`` runner that awaits a policy
with ``None`` for the (ignored) run context and event emitter — every policy
decides from the call + descriptor alone.
"""

from __future__ import annotations

from typing import Any

from loopplane.model import ToolCallRequest, ToolDescriptor


def call(tool_name: str, **input_kwargs: object) -> ToolCallRequest:
    return ToolCallRequest(call_id="c", tool_name=tool_name, input=dict(input_kwargs))


def descriptor(
    name: str = "t",
    *,
    source: str = "s",
    read_only: bool = False,
    concurrency_safe: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="d",
        input_schema={},
        concurrency_safe=concurrency_safe,
        read_only=read_only,
        source=source,
    )


async def decide(
    policy: Any, the_call: ToolCallRequest, the_descriptor: ToolDescriptor
) -> Any:
    """Await a policy decider with no-op run context / emitter (the policies ignore
    them) and return the verdict."""

    return await policy(the_call, the_descriptor, None, None)
