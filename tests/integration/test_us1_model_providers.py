"""Unit 020 US1: each adapter drives a real loop (text + tool-use) via a stub client."""

from __future__ import annotations

import json
from typing import Any

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig

from .conftest import ECHO_TOOL, EventCollector
from .provider_stubs import PROVIDERS, make_model

pytestmark = pytest.mark.anyio


def _mentions(value: Any, needle: str) -> bool:
    return needle in json.dumps(value, default=str)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_text_turn_streams_and_ends(provider: str) -> None:
    model, client = make_model(provider, [("text", "Hello from the model.")])
    host = LoopPlaneHost(RuntimeConfig(model=model))
    collector = EventCollector()

    outcome = await host.run("hi", collector)

    assert outcome.termination_reason == "natural-completion"
    assert outcome.turns_taken == 1
    assert len(client.calls) == 1
    assert any(
        getattr(event.payload, "text", None) == "Hello from the model."
        for event in collector.events
    )


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_tool_use_round_trip(provider: str) -> None:
    model, client = make_model(
        provider,
        [("tool", "call-1", "echo", {"text": "ping"}), ("text", "done")],
    )
    host = LoopPlaneHost(RuntimeConfig(model=model, tools=(ECHO_TOOL,)))
    collector = EventCollector()

    outcome = await host.run("use the tool", collector)

    assert outcome.termination_reason == "natural-completion"
    assert outcome.turns_taken == 2
    assert len(client.calls) == 2
    # The second model call carried the tool result back to the model. The request
    # field differs by wire format: OpenAI/Anthropic use "messages", Gemini "contents".
    request = client.calls[1]
    conversation = request.get("messages", request.get("contents"))
    assert _mentions(conversation, "ping")
    assert any(
        getattr(event.payload, "outcome", None) == "success"
        for event in collector.events
    )
