"""The Agent Loop turn cycle (FR-001–FR-008, FR-031).

Drives the model boundary, partitions tool calls by declared concurrency
safety, executes through the Gateway, emits normalized events, maintains
history, and ends every run with exactly one terminal event. With an
assembler attached, a context overflow compacts history and retries exactly
once before surfacing the failure (FR-008). The loop never persists,
formats, or authorizes (plan Architecture Boundaries).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import anyio.lowlevel

from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter
from loopplane.gateway.gateway import ToolGateway
from loopplane.hooks.decisions import PromptAnnotate, PromptBlock
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    LifecyclePoint,
    ModelStopPayload,
    UserPromptSubmitPayload,
)
from loopplane.loop.assembly import PromptAssembler
from loopplane.loop.compaction import compact_history
from loopplane.loop.history import SessionHistory
from loopplane.model.boundary import (
    ContextOverflowError,
    Message,
    ModelBoundary,
    ModelRequest,
    ReasoningIncrement,
    TextIncrement,
    ToolCallRequest,
    TurnEnd,
)
from loopplane.model.content import (
    ContentBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def partition_calls(
    calls: Sequence[ToolCallRequest],
    is_concurrency_safe: Callable[[str], bool],
) -> tuple[list[ToolCallRequest], list[ToolCallRequest]]:
    """Split a turn's calls into (concurrency-safe, sequential), each
    preserving the original request order (FR-005).
    """
    safe = [call for call in calls if is_concurrency_safe(call.tool_name)]
    sequential = [call for call in calls if not is_concurrency_safe(call.tool_name)]
    return safe, sequential


@dataclass
class _TurnOutcome:
    text_parts: list[str]
    calls: list[ToolCallRequest]
    turn_ended: bool


class AgentLoop:
    def __init__(
        self,
        *,
        model: ModelBoundary,
        gateway: ToolGateway,
        emitter: EventEmitter,
        history: SessionHistory,
        assembler: PromptAssembler | None = None,
        hooks: HookDispatcher | None = None,
    ) -> None:
        self._model = model
        self._gateway = gateway
        self._emitter = emitter
        self._history = history
        self._assembler = assembler
        # Optional lifecycle hooks (feature 015); absent by default (FR-011).
        self._hooks = hooks

    async def run(
        self, input_blocks: Sequence[ContentBlock], context: RunContext
    ) -> None:
        """One complete run: ends with exactly one run-terminated event (FR-001)."""
        run_start = len(self._history)
        turns_completed = 0
        prompt = "".join(
            block.text for block in input_blocks if isinstance(block, TextBlock)
        )

        if context.cancellation.is_set():
            await self._emitter.run_terminated("cancelled", 0)
            return
        if context.turn_budget is not None and context.turn_budget <= 0:
            await self._emitter.run_terminated("turn-budget-exhausted", 0)
            return

        # user-prompt-submit hook (feature 015): fire before the prompt is
        # recorded or sent. A block ends the run without a model call — the prompt
        # never enters history — and surfaces its public-safe reason as a
        # diagnostic; an annotation augments the prompt the model receives (FR-007).
        if self._hooks is not None:
            decision = await self._hooks.decide_prompt(
                UserPromptSubmitPayload(session_id=context.session_id, text=prompt)
            )
            if isinstance(decision, PromptBlock):
                await self._emitter.diagnostic("warning", "hooks", decision.reason)
                await self._emitter.run_terminated("cancelled", 0)
                return
            if isinstance(decision, PromptAnnotate):
                input_blocks = [*input_blocks, TextBlock(text=decision.text)]
                prompt = f"{prompt}\n{decision.text}"

        await self._history.append("user", input_blocks)
        await self._emitter.user_input(input_blocks)

        turn_index = 0
        while True:
            if context.cancellation.is_set():
                await self._terminate_cancelled(run_start, turns_completed)
                return
            if context.turn_budget is not None and turn_index >= context.turn_budget:
                await self._emitter.run_terminated(
                    "turn-budget-exhausted", turns_completed
                )
                return

            retried_after_overflow = False
            while True:
                request = self._assemble(prompt)
                try:
                    outcome = await self._stream_model_turn(
                        request, turn_index, context
                    )
                    break
                except ContextOverflowError:
                    # Compact and retry exactly once before surfacing (FR-008).
                    if (
                        self._assembler is None
                        or retried_after_overflow
                        or not compact_history(
                            self._history, keep_last=self._assembler.keep_last
                        )
                    ):
                        await self._emitter.run_terminated(
                            "unrecoverable-error", turns_completed
                        )
                        return
                    retried_after_overflow = True
                    self._assembler.mark_compacted()
                except Exception:
                    await self._emitter.run_terminated(
                        "unrecoverable-error", turns_completed
                    )
                    return

            if not outcome.turn_ended:
                # Cancelled while output was streaming (FR-003): keep any
                # partial output; never leave the input orphaned (FR-007).
                if outcome.text_parts:
                    await self._history.append(
                        "assistant", [TextBlock(text="".join(outcome.text_parts))]
                    )
                await self._terminate_cancelled(run_start, turns_completed)
                return

            turns_completed += 1
            assistant_blocks: list[ContentBlock] = []
            if outcome.text_parts:
                assistant_blocks.append(TextBlock(text="".join(outcome.text_parts)))
            assistant_blocks.extend(
                ToolCallBlock(
                    call_id=call.call_id, tool_name=call.tool_name, input=call.input
                )
                for call in outcome.calls
            )
            if assistant_blocks:
                await self._history.append("assistant", assistant_blocks)

            if not outcome.calls:
                if self._hooks is not None:
                    await self._hooks.fire(
                        LifecyclePoint.model_stop,
                        ModelStopPayload(
                            session_id=context.session_id,
                            turns_taken=turns_completed,
                        ),
                    )
                await self._emitter.run_terminated(
                    "natural-completion", turns_completed
                )
                return

            results = await self._execute_calls(outcome.calls, context)
            await self._history.append("user", results)
            turn_index += 1

    def _assemble(self, prompt: str) -> ModelRequest:
        tools = self._gateway.descriptors()
        if self._assembler is None:
            return ModelRequest(
                context=[
                    Message(role=entry.role, blocks=list(entry.blocks))
                    for entry in self._history.snapshot()
                ],
                tools=tools,
            )
        return self._assembler.assemble(
            history=self._history,
            tools=tools,
            capacity=self._model.context_capacity(),
            prompt=prompt,
        )

    async def _stream_model_turn(
        self, request: ModelRequest, turn_index: int, context: RunContext
    ) -> _TurnOutcome:
        outcome = _TurnOutcome(text_parts=[], calls=[], turn_ended=False)
        async for increment in self._model.stream_turn(request):
            if isinstance(increment, TextIncrement):
                outcome.text_parts.append(increment.text)
                await self._emitter.output_increment(increment.text, turn_index)
            elif isinstance(increment, ReasoningIncrement):
                await self._emitter.reasoning_increment(increment.text, turn_index)
            elif isinstance(increment, ToolCallRequest):
                outcome.calls.append(increment)
            elif isinstance(increment, TurnEnd):
                await self._emitter.turn_completed(
                    turn_index, increment.stop_reason, increment.usage
                )
                outcome.turn_ended = True
            await anyio.lowlevel.checkpoint()
            if context.cancellation.is_set():
                break
        return outcome

    async def _execute_calls(
        self, calls: Sequence[ToolCallRequest], context: RunContext
    ) -> list[ToolResultBlock]:
        safe, sequential = partition_calls(calls, self._gateway.is_concurrency_safe)
        outcomes: dict[str, ToolResultBlock] = {}
        for result in await self._gateway.execute_batch(
            safe, parallel=True, context=context, emitter=self._emitter
        ):
            outcomes[result.call_id] = result
        for result in await self._gateway.execute_batch(
            sequential, parallel=False, context=context, emitter=self._emitter
        ):
            outcomes[result.call_id] = result
        return [outcomes[call.call_id] for call in calls]

    async def _terminate_cancelled(self, run_start: int, turns_completed: int) -> None:
        if not self._history.has_assistant_entry_since(run_start):
            self._history.rollback_to(run_start)
        await self._emitter.run_terminated("cancelled", turns_completed)
