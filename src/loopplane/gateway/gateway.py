"""The Tool Gateway: the single chokepoint for tool resolution, validation,
authorization, execution, normalization, and size management
(contracts/tool-gateway.md; FR-020–FR-026).

Every call passes the same stages in order: resolve, validate, decide,
execute under a time limit, normalize, size-manage. Failure at any stage
produces an error-marked Tool Result; no stage failure ends the run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

import anyio

from loopplane.approval.decisions import (
    PolicyAllow,
    PolicyDecider,
    PolicyDeny,
    PolicyVerdict,
)
from loopplane.context import RunContext
from loopplane.errors import ErrorCategory, NormalizedError
from loopplane.events.emitter import EventEmitter
from loopplane.gateway.sizing import reduce_outputs
from loopplane.gateway.spi import AdapterOutput, ErrorOutput, ToolAdapter
from loopplane.gateway.validation import validate_input
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor
from loopplane.model.content import OutputBlock, ToolResultBlock

ToolHandler = Callable[
    [dict[str, object], RunContext], Awaitable[Sequence[OutputBlock]]
]

DEFAULT_CALL_TIMEOUT_SECONDS = 60.0
DEFAULT_OUTPUT_LIMIT_BYTES = 64 * 1024  # research A3


async def allow_all(
    call: ToolCallRequest,
    descriptor: ToolDescriptor,
    context: RunContext,
    emitter: EventEmitter,
) -> PolicyVerdict:
    """The default policy seam: every call is allowed (plan D1)."""
    return PolicyAllow()


class _HandlerAdapter:
    """Wraps a plain async handler as a single-tool adapter."""

    def __init__(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        self._descriptor = descriptor
        self._handler = handler

    def describe(self) -> Sequence[ToolDescriptor]:
        return [self._descriptor]

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        for block in await self._handler(call_input, context):
            yield block

    async def shutdown(self) -> None:
        return None


class _RegisteredTool:
    __slots__ = ("adapter", "descriptor")

    def __init__(self, descriptor: ToolDescriptor, adapter: ToolAdapter) -> None:
        self.descriptor = descriptor
        self.adapter = adapter


class ToolGateway:
    def __init__(
        self,
        *,
        decide: PolicyDecider | None = None,
        call_timeout_seconds: float | None = DEFAULT_CALL_TIMEOUT_SECONDS,
        output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
    ) -> None:
        self._registry: dict[str, _RegisteredTool] = {}
        self._decide: PolicyDecider = decide if decide is not None else allow_all
        self._call_timeout_seconds = call_timeout_seconds
        self._output_limit_bytes = output_limit_bytes

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        self._add(descriptor, _HandlerAdapter(descriptor, handler))

    def register_adapter(self, adapter: ToolAdapter) -> None:
        for descriptor in adapter.describe():
            self._add(descriptor, adapter)

    def _add(self, descriptor: ToolDescriptor, adapter: ToolAdapter) -> None:
        if descriptor.name in self._registry:
            raise ValueError(f"tool already registered: {descriptor.name}")
        self._registry[descriptor.name] = _RegisteredTool(descriptor, adapter)

    def descriptors(self) -> list[ToolDescriptor]:
        return [tool.descriptor for tool in self._registry.values()]

    def is_concurrency_safe(self, tool_name: str) -> bool:
        tool = self._registry.get(tool_name)
        if tool is None:
            return False
        return tool.descriptor.concurrency_safe

    async def execute_batch(
        self,
        calls: Sequence[ToolCallRequest],
        *,
        parallel: bool,
        context: RunContext,
        emitter: EventEmitter,
    ) -> list[ToolResultBlock]:
        """Execute one partition of a turn's calls.

        Emitted events keep the calls' original request order regardless of
        completion timing (FR-005): a parallel batch emits every
        `tool-call-started` in request order, executes concurrently, then
        emits every `tool-call-completed` in request order.
        """
        if not calls:
            return []
        if parallel and len(calls) > 1:
            return await self._execute_parallel(calls, context, emitter)
        return await self._execute_sequential(calls, context, emitter)

    async def _execute_sequential(
        self,
        calls: Sequence[ToolCallRequest],
        context: RunContext,
        emitter: EventEmitter,
    ) -> list[ToolResultBlock]:
        results: list[ToolResultBlock] = []
        for call in calls:
            await emitter.tool_call_started(call.call_id, call.tool_name, call.input)
            result, duration = await self._run_one(call, context, emitter)
            await self._emit_completed(emitter, result, duration)
            results.append(result)
        return results

    async def _execute_parallel(
        self,
        calls: Sequence[ToolCallRequest],
        context: RunContext,
        emitter: EventEmitter,
    ) -> list[ToolResultBlock]:
        for call in calls:
            await emitter.tool_call_started(call.call_id, call.tool_name, call.input)

        outcomes: dict[str, tuple[ToolResultBlock, float]] = {}

        async def run_into(call: ToolCallRequest) -> None:
            outcomes[call.call_id] = await self._run_one(call, context, emitter)

        async with anyio.create_task_group() as task_group:
            for call in calls:
                task_group.start_soon(run_into, call)

        results: list[ToolResultBlock] = []
        for call in calls:
            result, duration = outcomes[call.call_id]
            await self._emit_completed(emitter, result, duration)
            results.append(result)
        return results

    async def _run_one(
        self, call: ToolCallRequest, context: RunContext, emitter: EventEmitter
    ) -> tuple[ToolResultBlock, float]:
        started = anyio.current_time()

        def elapsed() -> float:
            return anyio.current_time() - started

        # Stage 1: resolve (FR-021).
        tool = self._registry.get(call.tool_name)
        if tool is None:
            return self._failure(
                call,
                NormalizedError(
                    category=ErrorCategory.UNKNOWN_TOOL,
                    reason=f"unknown tool: {call.tool_name}",
                ),
            ), elapsed()

        # Stage 2: validate before any execution (FR-022).
        problem = validate_input(tool.descriptor.input_schema, call.input)
        if problem is not None:
            return self._failure(
                call,
                NormalizedError(category=ErrorCategory.VALIDATION, reason=problem),
            ), elapsed()

        # Stage 3: decide (FR-023; contracts/approval.md).
        verdict = await self._decide(call, tool.descriptor, context, emitter)
        if isinstance(verdict, PolicyDeny):
            return self._failure(
                call,
                NormalizedError(
                    category=ErrorCategory.POLICY_DENIAL, reason=verdict.reason
                ),
            ), elapsed()

        # Stages 4–6: execute under the per-call time limit; normalize every
        # failure (FR-024, FR-025).
        outputs: list[OutputBlock] = []
        error: NormalizedError | None = None
        timed_out = False
        try:
            with anyio.move_on_after(self._call_timeout_seconds) as scope:
                async for output in tool.adapter.invoke(
                    call.tool_name, dict(call.input), context
                ):
                    if isinstance(output, ErrorOutput):
                        error = NormalizedError(
                            category=output.category, reason=output.message
                        )
                        break
                    outputs.append(output)
            timed_out = scope.cancelled_caught
        except Exception:
            error = NormalizedError(
                category=ErrorCategory.EXECUTION,
                reason=f"tool execution failed: {call.tool_name}",
            )
            await emitter.diagnostic(
                "warning", "gateway", f"{call.tool_name} raised an internal error"
            )
        if timed_out:
            error = NormalizedError(
                category=ErrorCategory.TIMEOUT,
                reason=(
                    f"{call.tool_name} exceeded its "
                    f"{self._call_timeout_seconds}s execution time limit"
                ),
            )
            await emitter.diagnostic(
                "warning", "gateway", f"{call.tool_name} exceeded its time limit"
            )
        if error is not None:
            return self._failure(call, error, outputs), elapsed()

        # Stage 7: size-manage (FR-026).
        outputs = reduce_outputs(outputs, self._output_limit_bytes)
        result = ToolResultBlock(
            call_id=call.call_id, outcome="success", outputs=outputs
        )
        return result, elapsed()

    @staticmethod
    def _failure(
        call: ToolCallRequest,
        error: NormalizedError,
        outputs: Sequence[OutputBlock] = (),
    ) -> ToolResultBlock:
        return ToolResultBlock(
            call_id=call.call_id, outcome="failure", outputs=list(outputs), error=error
        )

    @staticmethod
    async def _emit_completed(
        emitter: EventEmitter, result: ToolResultBlock, duration: float
    ) -> None:
        await emitter.tool_call_completed(
            call_id=result.call_id,
            outcome=result.outcome,
            outputs=result.outputs,
            duration_seconds=duration,
            error=result.error,
        )
