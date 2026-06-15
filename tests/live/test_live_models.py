"""Unit 020: opt-in, secret-gated live model checks.

Excluded from the default CI gates: each test is skipped unless its provider API key and
an explicit model name are set in the environment. Run manually, e.g.::

    ANTHROPIC_API_KEY=... LOOPPLANE_ANTHROPIC_MODEL=<model> uv run pytest tests/live
    OPENAI_API_KEY=...    LOOPPLANE_OPENAI_MODEL=<model>    uv run pytest tests/live
"""

from __future__ import annotations

import os

import pytest

from loopplane.events import RuntimeEvent
from loopplane.host import LoopPlaneHost, RuntimeConfig

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@pytest.mark.skipif(
    not (
        os.environ.get("ANTHROPIC_API_KEY")
        and os.environ.get("LOOPPLANE_ANTHROPIC_MODEL")
    ),
    reason="set ANTHROPIC_API_KEY and LOOPPLANE_ANTHROPIC_MODEL to run the live check",
)
async def test_anthropic_live_text_turn() -> None:
    from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel

    model = AnthropicModel(
        AnthropicConfig(model=os.environ["LOOPPLANE_ANTHROPIC_MODEL"])
    )
    host = LoopPlaneHost(RuntimeConfig(model=model))
    outcome = await host.run("Reply with the single word: pong.", _Collector())
    assert outcome.termination_reason == "natural-completion"


@pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("LOOPPLANE_OPENAI_MODEL")),
    reason="set OPENAI_API_KEY and LOOPPLANE_OPENAI_MODEL to run the live check",
)
async def test_openai_live_text_turn() -> None:
    from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

    model = OpenAIModel(OpenAIConfig(model=os.environ["LOOPPLANE_OPENAI_MODEL"]))
    host = LoopPlaneHost(RuntimeConfig(model=model))
    outcome = await host.run("Reply with the single word: pong.", _Collector())
    assert outcome.termination_reason == "natural-completion"
