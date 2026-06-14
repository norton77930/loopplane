"""Model provider selection for the CLI (spec FR-005, FR-006; research R4).

Credential-free by default: a stateless ``DemoModel`` that emits one canned
response per turn, never exhausts, and never touches the network. A real model is
opt-in via ``LOOPPLANE_MODEL="module:function"`` naming an importable
``ModelBoundary`` builder; a bad reference falls back to the demo and never echoes a
credential.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Mapping

from loopplane.model import (
    ModelBoundary,
    ModelIncrement,
    ModelRequest,
    TextIncrement,
    TokenUsage,
    TurnEnd,
)

DEMO_RESPONSE = (
    "LoopPlane demo model: no provider is configured, so this is a canned offline "
    "response. Set LOOPPLANE_MODEL to a 'module:function' ModelBoundary builder to "
    "use a real model."
)


class DemoModel:
    """A stateless, credential-free model: one canned text turn per request."""

    def __init__(self, response: str = DEMO_RESPONSE) -> None:
        self._response = response

    def context_capacity(self) -> int:
        return 1_000_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        yield TextIncrement(text=self._response)
        yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())


def select_model(env: Mapping[str, str]) -> ModelBoundary:
    """The demo model unless ``env`` names an importable ``module:function`` builder."""
    reference = env.get("LOOPPLANE_MODEL")
    if not reference or ":" not in reference:
        return DemoModel()
    module_name, _, attr = reference.partition(":")
    try:
        builder = getattr(importlib.import_module(module_name), attr)
        model = builder()
    except Exception:
        return DemoModel()  # a bad reference falls back; never echoes a credential
    if not isinstance(model, ModelBoundary):
        return DemoModel()
    return model
