"""Shared in-process harness for the Web / API Host suites (011).

A public-safe, credential-free fake model + host builder + authenticators + an
in-process Starlette ``TestClient`` factory. No real socket is bound and no
external network is used (NFR-006/NFR-007).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from collections.abc import Awaitable, Callable  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from loopplane.context import RunContext  # noqa: E402
from loopplane.host import (  # noqa: E402
    ApprovalPolicy,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
    ToolSpec,
)
from loopplane.model import (  # noqa: E402
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)
from loopplane.webapi.auth import Principal  # noqa: E402

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
    platform_fairness: object | None = None,
) -> LoopPlaneHost:
    """A ``LoopPlaneHost`` over the fake model + echo tool, scoped to a tmp dir.

    With ``storage=True`` a durable checkpoint/artifact store is configured (so
    list / history / resume have records to read).
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
            platform_fairness=platform_fairness,
        ),
        working_scope=working_scope,
    )


# --- authenticators (credential-free, public-safe) ---------------------------

Authenticator = Callable[[str | None], Awaitable[Principal | None]]

VALID = "let-me-in"


async def allow_all(credential: str | None) -> Principal | None:
    return Principal(id="anyone")


async def deny_all(credential: str | None) -> Principal | None:
    return None


async def accept_valid(credential: str | None) -> Principal | None:
    return Principal(id="valid-user") if credential == VALID else None


async def raising(credential: str | None) -> Principal | None:
    raise RuntimeError("authenticator failure")


# --- client factory ----------------------------------------------------------


def make_client(app: FastAPI) -> TestClient:
    """An in-process client over the ASGI app — no real socket is bound."""

    return TestClient(app)
