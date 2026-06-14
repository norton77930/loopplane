"""US3: run follow-up work when the model stops (T015; FR-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.hooks import HookRegistry, LifecyclePoint, ModelStopPayload
from loopplane.model import TextBlock
from tests.hooks_helpers import Recorder, build_with_hooks, text_script

pytestmark = pytest.mark.anyio


async def test_model_stop_fires_once_at_natural_completion(tmp_path: Path) -> None:
    registry = HookRegistry()
    stops: list[ModelStopPayload] = []
    registry.register(LifecyclePoint.model_stop, stops.append)
    controller, sid, _ = build_with_hooks(
        text_script("done"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="hi")])
    assert len(stops) == 1
    assert stops[0].turns_taken == 1
