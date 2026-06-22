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
from decimal import Decimal

import anyio.lowlevel

from loopplane.budget import BudgetChecker
from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter
from loopplane.fairness import PlatformFairnessGate
from loopplane.gateway.gateway import ToolGateway
from loopplane.hooks.decisions import PromptAnnotate, PromptBlock
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    LifecyclePoint,
    ModelStopPayload,
    UserPromptSubmitPayload,
)
from loopplane.loop.assembly import PromptAssembler, estimate_request_tokens
from loopplane.loop.compaction import compact_history
from loopplane.loop.history import HistoryEntry, SessionHistory
from loopplane.loop.summarizer import summarize_compaction
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
    SummaryMarkerBlock,
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
        summarizer: ModelBoundary | None = None,
        budget_checker: BudgetChecker | None = None,
        platform_fairness: PlatformFairnessGate | None = None,
    ) -> None:
        self._model = model
        self._gateway = gateway
        self._emitter = emitter
        self._history = history
        self._assembler = assembler
        # Optional lifecycle hooks (feature 015); absent by default (FR-011).
        self._hooks = hooks
        # Optional cheap-model compaction summarizer (spec 042); absent by default.
        # A FAIL-SAFE overlay on the mechanical digest: any failure keeps the
        # mechanical marker, so a summarizer can never break a run.
        self._summarizer = summarizer
        # Optional USD budget checker (spec 055; ADR 0005); None by default → no cost
        # accounting and a byte-identical run. When set, the loop records each turn's
        # USD cost from TurnEnd.usage and terminates the run `budget-exceeded` after the
        # turn that crosses a per-message/per-session cap (output retained). Built only
        # when caps + a pricing table + a model-id are configured (loopplane.budget is a
        # foundational package, not the tools layer — so the gateway audit is intact).
        self._budget_checker = budget_checker
        self._platform_fairness = platform_fairness

    def current_session_cost(self) -> Decimal | None:
        """The session's accumulated USD, or ``None`` when no budget checker is
        configured (064 cost surfacing; read-only — no run-path effect)."""
        if self._budget_checker is None:
            return None
        return self._budget_checker.session_spent

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
        # Reset the per-message USD accumulator; the per-session total persists across
        # runs on the same session (spec 055). No-op when no checker is configured.
        if self._budget_checker is not None:
            self._budget_checker.start_run()

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
                before = self._history.snapshot()
                request = self._assemble(prompt, context.output_schema)
                # Proactive compaction (spec 041) happens inside the synchronous
                # `assemble`; if a summarizer is configured and a compaction just
                # occurred, augment the fresh marker with a model summary and
                # recompose so the model sees it (spec 042; FAIL-SAFE overlay).
                if (
                    self._summarizer is not None
                    and self._assembler is not None
                    and self._assembler.take_compacted()
                ):
                    await self._summarize_compaction(before)
                    request = self._assemble(prompt, context.output_schema)
                if (
                    self._budget_checker is not None
                    and self._budget_checker.pre_turn_enabled()
                    and self._budget_checker.pre_turn_exceeded(
                        estimate_request_tokens(request)
                    )
                ):
                    await self._emitter.run_terminated(
                        "budget-exceeded", turns_completed
                    )
                    return
                try:
                    outcome = await self._stream_model_turn(
                        request, turn_index, context
                    )
                    break
                except ContextOverflowError:
                    # Compact and retry exactly once before surfacing (FR-008).
                    before_overflow = self._history.snapshot()
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
                    # Augment the fresh marker with a model summary before the
                    # retry recomposes (spec 042; FAIL-SAFE overlay).
                    if self._summarizer is not None:
                        await self._summarize_compaction(before_overflow)
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
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    input=call.input,
                    provider_signature=call.provider_signature,
                )
                for call in outcome.calls
            )
            if assistant_blocks:
                await self._history.append("assistant", assistant_blocks)

            # USD budget enforcement (spec 055; ADR 0005): the just-finished turn's cost
            # was recorded in `_stream_model_turn`; if a per-message/per-session cap is
            # now crossed, terminate after this turn (output retained above) — distinct
            # from `cancelled` (input-stranding) and `turn-budget-exhausted` (by count).
            # Skipped entirely when no checker is configured → byte-identical.
            if self._budget_checker is not None and self._budget_checker.exceeded():
                await self._emitter.run_terminated("budget-exceeded", turns_completed)
                return

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

    def _assemble(
        self, prompt: str, output_schema: dict[str, object] | None = None
    ) -> ModelRequest:
        tools = self._gateway.descriptors()
        if self._assembler is None:
            return ModelRequest(
                context=[
                    Message(role=entry.role, blocks=list(entry.blocks))
                    for entry in self._history.snapshot()
                ],
                tools=tools,
                output_schema=output_schema,
            )
        return self._assembler.assemble(
            history=self._history,
            tools=tools,
            capacity=self._model.context_capacity(),
            prompt=prompt,
            output_schema=output_schema,
        )

    async def _summarize_compaction(self, before: tuple[HistoryEntry, ...]) -> None:
        """FAIL-SAFE overlay (spec 042): augment the just-produced mechanical
        summary marker with a model-written summary of the dropped span. The
        marker is the first in-memory entry's first block (compaction placed it
        there via `replace_prefix`); the dropped span is the prefix of `before`
        that the marker replaced. Any summarizer failure is swallowed by
        `summarize_compaction`, so the mechanical marker stands and the run is
        never affected.
        """
        if self._summarizer is None:
            return
        after = self._history.snapshot()
        if not after:
            return
        marker_block = after[0].blocks[0] if after[0].blocks else None
        if not isinstance(marker_block, SummaryMarkerBlock):
            return
        # `replace_prefix(keep_from, marker)` collapsed `before[:keep_from]` into
        # the single marker, so keep_from = len(before) - (len(after) - 1).
        keep_from = len(before) - (len(after) - 1)
        dropped = before[:keep_from] if keep_from > 0 else before
        augmented = await summarize_compaction(
            summarizer=self._summarizer, dropped=dropped, marker=marker_block
        )
        if augmented is marker_block:
            return  # the summarizer failed; the mechanical marker stands
        self._history.replace_entry(
            0,
            HistoryEntry(
                role=after[0].role,
                blocks=(augmented,),
                recorded_at=after[0].recorded_at,
            ),
        )

    async def _stream_model_turn(
        self, request: ModelRequest, turn_index: int, context: RunContext
    ) -> _TurnOutcome:
        if self._platform_fairness is not None and context.principal_id is not None:
            async with self._platform_fairness.model_turn(context.principal_id):
                return await self._stream_model_turn_now(request, turn_index, context)
        return await self._stream_model_turn_now(request, turn_index, context)

    async def _stream_model_turn_now(
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
                # USD budget accounting (spec 055; ADR 0005): record this turn's cost. A
                # fail-soft `None` (model has no price) accumulates nothing and emits a
                # public-safe warning; the cap is just not enforced for that turn. No-op
                # when no checker is configured → byte-identical.
                if self._budget_checker is not None:
                    cost = await self._budget_checker.record_turn(increment.usage)
                    if cost is None:
                        await self._emitter.diagnostic(
                            "warning",
                            "budget",
                            "model has no configured price; the USD budget cap is "
                            "not enforced for this turn",
                        )
                    elif self._budget_checker.ledger_unavailable:
                        # 063 fail-open (ADR 0010 D9): the durable monthly ledger was
                        # unreachable; allow the turn but flag that the monthly cap was
                        # not enforced (public-safe — no id/amount interpolated).
                        await self._emitter.diagnostic(
                            "warning",
                            "budget",
                            "the usage ledger is unavailable; the per-user monthly "
                            "cap is not enforced for this turn",
                        )
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
