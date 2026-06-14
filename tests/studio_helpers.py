"""Shared in-process harness for the Desktop / Studio Host suites (012).

A public-safe, deterministic fake model + host builder + an auto-approve handler.
No GUI / transport — pure in-process over the host.
"""

from __future__ import annotations

from pathlib import Path

from loopplane.context import RunContext
from loopplane.host import (
    ApprovalDecision,
    ApprovalPolicy,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
    ToolSpec,
)
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

# --- a public-safe echo tool -------------------------------------------------

ECHO_DESCRIPTOR = ToolDescriptor(
    name="echo",
    description="Echo the input text back.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    concurrency_safe=True,
    read_only=True,
)


async def echo_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text=str(call_input["text"]))]


ECHO_TOOL = ToolSpec(descriptor=ECHO_DESCRIPTOR, handler=echo_handler)


# --- fake models -------------------------------------------------------------


def text_model(text: str = "hello") -> ScriptedModel:
    """One plain-text turn ending the run."""

    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )


def multi_text_model(*texts: str) -> ScriptedModel:
    """One text turn per argument — enough script for several sequential runs."""

    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=t)]) for t in texts],
        context_capacity=100_000,
    )


def tool_then_text_model(tool_name: str = "echo") -> ScriptedModel:
    """A tool-calling turn followed by a closing text turn."""

    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    TextIncrement(text="using a tool"),
                    ToolCallRequest(
                        call_id="c1", tool_name=tool_name, input={"text": "hello"}
                    ),
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="done")]),
        ],
        context_capacity=100_000,
    )


# --- host builder ------------------------------------------------------------


def build_test_host(
    working_scope: Path,
    *,
    model: ScriptedModel | None = None,
    tools: tuple[ToolSpec, ...] = (ECHO_TOOL,),
    approval: ApprovalPolicy | None = None,
    storage: bool = False,
) -> LoopPlaneHost:
    """A ``LoopPlaneHost`` over the fake model + echo tool, scoped to a tmp dir.

    With ``storage=True`` a durable checkpoint/artifact store is configured (so
    list / history have records to read).
    """

    store: StorageConfig | None = None
    if storage:
        root = working_scope / "store"
        root.mkdir(parents=True, exist_ok=True)
        store = StorageConfig(root=root)
    return LoopPlaneHost(
        RuntimeConfig(
            model=model or tool_then_text_model(),
            tools=tools,
            approval=approval,
            storage=store,
        ),
        working_scope=working_scope,
    )


# --- an auto-approve handler (for interactive sessions) ----------------------


async def auto_approve(payload: object) -> ApprovalDecision:
    """An ``on_approval`` handler that approves every request — admits a tool
    gated as ``ask`` so an interactive run reaches completion in-process."""

    return ApprovalDecision(allow=True)
