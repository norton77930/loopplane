"""US4: screen or annotate a prompt before the model sees it (T017; FR-007, SC-006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.hooks import HookRegistry, LifecyclePoint, PromptAnnotate, PromptBlock
from loopplane.model import TextBlock
from tests.hooks_helpers import Recorder, build_with_hooks, text_script

pytestmark = pytest.mark.anyio


async def test_prompt_block_prevents_the_model_call(tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register(
        LifecyclePoint.user_prompt_submit, lambda _p: PromptBlock(reason="moderated")
    )
    recorder = Recorder()
    controller, sid, _ = build_with_hooks(
        text_script("done"), recorder, registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="bad prompt")])
    assert "assistant-output-increment" not in recorder.types  # model not invoked
    assert "user-input" not in recorder.types  # blocked before the prompt is recorded
    terminal = recorder.events[-1]
    assert terminal.type == "run-terminated"
    assert terminal.payload.reason == "cancelled"
    diagnostic = next(e for e in recorder.events if e.type == "diagnostic")
    assert diagnostic.payload.message == "moderated"  # public-safe reason surfaced


async def test_prompt_annotate_augments_the_recorded_prompt(tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register(
        LifecyclePoint.user_prompt_submit,
        lambda _p: PromptAnnotate(text="EXTRA-CONTEXT"),
    )
    controller, sid, _ = build_with_hooks(
        text_script("done"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="hi")])
    user_blocks = controller.history_snapshot(sid)[0].blocks
    assert (
        TextBlock(text="EXTRA-CONTEXT") in user_blocks
    )  # the model sees the annotation
