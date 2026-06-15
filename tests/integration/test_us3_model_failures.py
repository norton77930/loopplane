"""Unit 020 US3: provider faults are public-safe; token usage is reported."""

from __future__ import annotations

import pytest

from loopplane.adapters._model_errors import ModelProviderError
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import Message, ModelRequest, TextBlock

from .conftest import EventCollector
from .provider_stubs import PROVIDERS, StubAPIError, make_failing_model, make_model

pytestmark = pytest.mark.anyio

_SECRET = "sk-do-not-leak-0123456789abcdef"


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_adapter_error_is_public_safe(provider: str) -> None:
    error = StubAPIError(f"upstream said {_SECRET}", status_code=500)
    model, _ = make_failing_model(provider, error)
    request = ModelRequest(
        context=[Message(role="user", blocks=[TextBlock(text="hi")])]
    )

    with pytest.raises(ModelProviderError) as caught:
        async for _increment in model.stream_turn(request):
            pass

    assert _SECRET not in str(caught.value)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_loop_hides_provider_error_from_events(provider: str) -> None:
    error = StubAPIError(f"upstream said {_SECRET}", status_code=500)
    model, _ = make_failing_model(provider, error)
    host = LoopPlaneHost(RuntimeConfig(model=model))
    collector = EventCollector()

    outcome = await host.run("hi", collector)

    assert outcome.termination_reason == "unrecoverable-error"
    for event in collector.events:
        assert _SECRET not in str(event)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_usage_is_reported(provider: str) -> None:
    model, _ = make_model(provider, [("text", "hello")])
    host = LoopPlaneHost(RuntimeConfig(model=model))
    collector = EventCollector()

    await host.run("hi", collector)

    usages = [
        event.payload.usage
        for event in collector.events
        if getattr(event.payload, "usage", None) is not None
    ]
    assert usages
    assert usages[0].input_tokens == 11
    assert usages[0].output_tokens == 7
