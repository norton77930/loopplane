"""The hook dispatcher: fires observational points and resolves gating points
from a registry (FR-005, FR-016, FR-017; research R4/R5/R7).

A dispatcher is built per session from the shared registry plus an optional
``on_failure`` sink. It snapshots a point's callbacks before firing (FR-018),
detects coroutine callbacks (FR-004), and isolates every failure so a misbehaving
hook can neither crash the run nor leak detail (FR-005, FR-015): a raising
callback is skipped and reported through ``on_failure`` with a public-safe message
naming only the point.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import replace

from loopplane.hooks.decisions import (
    PromptAllow,
    PromptAnnotate,
    PromptBlock,
    PromptDecision,
    ToolGateAllow,
    ToolGateDecision,
    ToolGateDeny,
    ToolGateModify,
)
from loopplane.hooks.points import (
    BeforeToolUsePayload,
    LifecyclePoint,
    UserPromptSubmitPayload,
)
from loopplane.hooks.registry import HookCallback, HookRegistry

#: Reports a public-safe, metadata-only message when a hook misbehaves. The
#: runtime wires this to the session emitter's ``diagnostic`` (Constitution VI).
OnFailure = Callable[[str], Awaitable[None]]


class HookDispatcher:
    def __init__(
        self, registry: HookRegistry, *, on_failure: OnFailure | None = None
    ) -> None:
        self._registry = registry
        self._on_failure = on_failure

    async def _invoke(self, callback: HookCallback, payload: object) -> object:
        result = callback(payload)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _report(self, point: LifecyclePoint) -> None:
        if self._on_failure is not None:
            await self._on_failure(f"a hook for {point.value} failed and was skipped")

    async def fire(self, point: LifecyclePoint, payload: object) -> None:
        """Run every observational callback in order, isolating failures (FR-005)."""
        for callback in self._registry.callbacks(point):
            try:
                await self._invoke(callback, payload)
            except Exception:
                await self._report(point)

    async def decide_tool(self, payload: BeforeToolUsePayload) -> ToolGateDecision:
        """Resolve before-tool callbacks: deny wins; modifications compose in
        order; a raising/malformed hook abstains (FR-016, FR-017).
        """
        current_input = dict(payload.input)
        modified = False
        for callback in self._registry.callbacks(LifecyclePoint.before_tool_use):
            try:
                result = await self._invoke(
                    callback, replace(payload, input=dict(current_input))
                )
            except Exception:
                await self._report(LifecyclePoint.before_tool_use)
                continue
            if isinstance(result, ToolGateDeny):
                return result
            if isinstance(result, ToolGateModify):
                current_input = dict(result.input)
                modified = True
            # ToolGateAllow / None / anything else -> abstain (no change).
        return ToolGateModify(input=current_input) if modified else ToolGateAllow()

    async def decide_prompt(self, payload: UserPromptSubmitPayload) -> PromptDecision:
        """Resolve prompt-submit callbacks: block wins; annotations compose in
        order (a later hook sees the accumulated text); failures abstain.
        """
        base = payload.text
        annotations: list[str] = []
        for callback in self._registry.callbacks(LifecyclePoint.user_prompt_submit):
            seen = base if not annotations else base + "\n" + "\n".join(annotations)
            try:
                result = await self._invoke(callback, replace(payload, text=seen))
            except Exception:
                await self._report(LifecyclePoint.user_prompt_submit)
                continue
            if isinstance(result, PromptBlock):
                return result
            if isinstance(result, PromptAnnotate):
                annotations.append(result.text)
            # PromptAllow / None / anything else -> abstain.
        if annotations:
            return PromptAnnotate(text="\n".join(annotations))
        return PromptAllow()
