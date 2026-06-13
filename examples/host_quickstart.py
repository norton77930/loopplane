"""Embedding example and minimal smoke runner for the LoopPlane host interface.

Developer-focused: it builds a :class:`RuntimeConfig`, constructs a
``LoopPlaneHost``, drives one fixed scripted scenario, and prints the ordered
event stream and outcome. It runs with the scripted model and needs no
credentials or network. It is deliberately minimal and is **not** a product CLI
(FR-030–FR-033, FR-051).

Usage::

    python examples/host_quickstart.py [text|tool|durable]
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import anyio

from loopplane.host import (
    LoopPlaneHost,
    RunOutcome,
    RuntimeConfig,
    StorageConfig,
    ToolSpec,
)
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

_ECHO = ToolDescriptor(
    name="echo",
    description="Echo the given text back.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)

SCENARIOS = ("text", "tool", "durable")


async def _echo(call_input: dict[str, object], context: object) -> list[TextBlock]:
    return [TextBlock(text=str(call_input["text"]))]


def _text_config() -> RuntimeConfig:
    return RuntimeConfig(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[TextIncrement(text="Hello from LoopPlane.")]
                )
            ],
            context_capacity=100_000,
        )
    )


def _tool_config() -> RuntimeConfig:
    return RuntimeConfig(
        model=ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[
                        TextIncrement(text="Let me echo that."),
                        ToolCallRequest(
                            call_id="c1", tool_name="echo", input={"text": "hello"}
                        ),
                    ],
                    stop_reason="tool-use",
                ),
                ScriptedTurn(increments=[TextIncrement(text="The tool said: hello")]),
            ],
            context_capacity=100_000,
        ),
        tools=(ToolSpec(descriptor=_ECHO, handler=_echo),),
    )


def _durable_config(root: Path) -> RuntimeConfig:
    base = _tool_config()
    return RuntimeConfig(
        model=base.model, tools=base.tools, storage=StorageConfig(root=root)
    )


async def run_scenario(
    name: str,
    *,
    working_scope: Path | None = None,
    storage_root: Path | None = None,
) -> RunOutcome:
    """Drive one named scenario through ``LoopPlaneHost`` and print its stream."""

    if name not in SCENARIOS:
        raise ValueError(
            f"unknown scenario {name!r}; choose one of {', '.join(SCENARIOS)}"
        )
    scope = working_scope or Path.cwd()
    if name == "durable":
        config = _durable_config(storage_root or scope / "loopplane-data")
    elif name == "tool":
        config = _tool_config()
    else:
        config = _text_config()

    host = LoopPlaneHost(config, working_scope=scope)
    lines: list[str] = []

    async def on_event(event: object) -> None:
        lines.append(f"{event.sequence:>3}  {event.type}")  # type: ignore[attr-defined]

    outcome = await host.run("please run the scenario", on_event)
    for line in lines:
        print(line)
    print(f"ended: {outcome.termination_reason}")
    return outcome


async def _drive(name: str, scope: Path) -> RunOutcome:
    return await run_scenario(name, working_scope=scope)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    name = args[0] if args else "tool"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            anyio.run(_drive, name, Path(tmp))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
