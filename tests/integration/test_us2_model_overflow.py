"""Unit 020 US2: each adapter raises ContextOverflowError; loop ends unrecoverable."""

from __future__ import annotations

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import Message, ModelRequest, TextBlock
from loopplane.model.boundary import ContextOverflowError

from .conftest import EventCollector
from .provider_stubs import PROVIDERS, make_failing_model, overflow_error

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_adapter_raises_context_overflow(provider: str) -> None:
    model, _ = make_failing_model(provider, overflow_error(provider))
    request = ModelRequest(
        context=[Message(role="user", blocks=[TextBlock(text="hi")])]
    )

    with pytest.raises(ContextOverflowError):
        async for _increment in model.stream_turn(request):
            pass


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_loop_terminates_unrecoverable_on_persistent_overflow(
    provider: str,
) -> None:
    model, _ = make_failing_model(provider, overflow_error(provider))
    host = LoopPlaneHost(RuntimeConfig(model=model))
    collector = EventCollector()

    outcome = await host.run("hi", collector)

    assert outcome.termination_reason == "unrecoverable-error"
