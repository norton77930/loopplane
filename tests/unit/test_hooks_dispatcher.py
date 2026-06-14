"""Unit tests for the hook dispatcher (T005; FR-004, FR-005, FR-016, FR-017,
FR-018)."""

from __future__ import annotations

import pytest

from loopplane.hooks import (
    BeforeToolUsePayload,
    HookRegistry,
    LifecyclePoint,
    ModelStopPayload,
    PromptAllow,
    PromptAnnotate,
    PromptBlock,
    ToolGateAllow,
    ToolGateDeny,
    ToolGateModify,
    UserPromptSubmitPayload,
)
from loopplane.hooks.dispatcher import HookDispatcher

pytestmark = pytest.mark.anyio

OBS = LifecyclePoint.after_tool_use
TOOL = LifecyclePoint.before_tool_use
PROMPT = LifecyclePoint.user_prompt_submit


def _obs_payload() -> ModelStopPayload:
    return ModelStopPayload(session_id="s", turns_taken=1)


def _tool_payload(**inputs: object) -> BeforeToolUsePayload:
    return BeforeToolUsePayload(
        session_id="s", call_id="c", tool_name="t", input=dict(inputs)
    )


def _build() -> tuple[HookRegistry, HookDispatcher, list[str]]:
    registry = HookRegistry()
    failures: list[str] = []

    async def on_failure(message: str) -> None:
        failures.append(message)

    return registry, HookDispatcher(registry, on_failure=on_failure), failures


async def test_fire_runs_all_callbacks_in_order() -> None:
    registry, dispatcher, _ = _build()
    seen: list[int] = []

    def first(_p: object) -> None:
        seen.append(1)

    async def second(_p: object) -> None:
        seen.append(2)

    registry.register(OBS, first)
    registry.register(OBS, second)
    await dispatcher.fire(OBS, _obs_payload())
    assert seen == [1, 2]  # sync + async both run, in order (FR-003/FR-004)


async def test_fire_isolates_failure_without_leaking_detail() -> None:
    registry, dispatcher, failures = _build()
    survived: list[int] = []

    def boom(_p: object) -> None:
        raise RuntimeError("secret-detail-xyz")

    registry.register(OBS, boom)
    registry.register(OBS, lambda _p: survived.append(1))
    await dispatcher.fire(OBS, _obs_payload())
    assert survived == [1]  # later hook still ran (FR-005)
    assert len(failures) == 1
    assert "after_tool_use" in failures[0]
    assert "secret-detail-xyz" not in failures[0]  # no raw exception leak (FR-015)


async def test_decide_tool_deny_wins() -> None:
    registry, dispatcher, _ = _build()
    registry.register(TOOL, lambda _p: ToolGateModify(input={"a": 1}))
    registry.register(TOOL, lambda _p: ToolGateDeny(reason="no"))
    decision = await dispatcher.decide_tool(_tool_payload())
    assert isinstance(decision, ToolGateDeny)
    assert decision.reason == "no"


async def test_decide_tool_modifications_compose_in_order() -> None:
    registry, dispatcher, _ = _build()
    seen_by_second: dict[str, object] = {}

    registry.register(TOOL, lambda p: ToolGateModify(input={**p.input, "a": 1}))

    def second(p: BeforeToolUsePayload) -> ToolGateModify:
        seen_by_second.update(p.input)
        return ToolGateModify(input={**p.input, "b": 2})

    registry.register(TOOL, second)
    decision = await dispatcher.decide_tool(_tool_payload())
    assert isinstance(decision, ToolGateModify)
    assert decision.input == {"a": 1, "b": 2}
    assert seen_by_second == {"a": 1}  # later hook saw the earlier modification


async def test_decide_tool_failure_and_garbage_abstain() -> None:
    registry, dispatcher, failures = _build()

    def boom(_p: object) -> ToolGateDeny:
        raise RuntimeError("x")

    registry.register(TOOL, boom)
    registry.register(TOOL, lambda _p: "garbage")  # unrecognized -> abstain
    decision = await dispatcher.decide_tool(_tool_payload())
    assert isinstance(decision, ToolGateAllow)  # never fails open, never aborts
    assert len(failures) == 1


async def test_decide_prompt_block_wins() -> None:
    registry, dispatcher, _ = _build()
    registry.register(PROMPT, lambda _p: PromptAnnotate(text="ctx"))
    registry.register(PROMPT, lambda _p: PromptBlock(reason="nope"))
    decision = await dispatcher.decide_prompt(
        UserPromptSubmitPayload(session_id="s", text="hi")
    )
    assert isinstance(decision, PromptBlock)


async def test_decide_prompt_annotations_compose_and_accumulate() -> None:
    registry, dispatcher, _ = _build()
    seen_text: list[str] = []

    registry.register(PROMPT, lambda _p: PromptAnnotate(text="A"))

    def second(p: UserPromptSubmitPayload) -> PromptAnnotate:
        seen_text.append(p.text)
        return PromptAnnotate(text="B")

    registry.register(PROMPT, second)
    decision = await dispatcher.decide_prompt(
        UserPromptSubmitPayload(session_id="s", text="base")
    )
    assert isinstance(decision, PromptAnnotate)
    assert decision.text == "A\nB"
    assert seen_text == ["base\nA"]  # later hook saw base + earlier annotation


async def test_decide_prompt_no_hooks_allows() -> None:
    _registry, dispatcher, _ = _build()
    decision = await dispatcher.decide_prompt(
        UserPromptSubmitPayload(session_id="s", text="hi")
    )
    assert isinstance(decision, PromptAllow)


async def test_registration_midfire_does_not_affect_inflight() -> None:
    registry, dispatcher, _ = _build()
    seen: list[str] = []

    def adder(_p: object) -> None:
        registry.register(OBS, lambda _q: seen.append("new"))
        seen.append("orig")

    registry.register(OBS, adder)
    await dispatcher.fire(OBS, _obs_payload())
    assert seen == ["orig"]  # the mid-fire registration did not run this fire
    await dispatcher.fire(OBS, _obs_payload())
    assert "new" in seen  # it runs on the next fire
