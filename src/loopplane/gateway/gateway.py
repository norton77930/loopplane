"""The skeletal Tool Gateway: registry, name resolution, execution, an
allow-all policy seam, and `tool-call-*` event emission (plan D1; FR-020,
FR-021).

The Gateway is the single chokepoint for everything tool-related; later
phases add the remaining pipeline stages (validation, decision, timeout,
normalization detail, size management) inside it. Failure at any stage
produces an error-marked Tool Result; no stage failure ends the run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import anyio

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory, NormalizedError
from loopplane.events.emitter import EventEmitter
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor
from loopplane.model.content import OutputBlock, ToolResultBlock

ToolHandler = Callable[
    [dict[str, object], RunContext], Awaitable[Sequence[OutputBlock]]
]

PolicyDecision = Literal["allow", "deny"]
PolicyDecider = Callable[[ToolCallRequest, RunContext], Awaitable[PolicyDecision]]


async def allow_all(call: ToolCallRequest, context: RunContext) -> PolicyDecision:
    """The default policy seam: every call is allowed (plan D1)."""
    return "allow"


@dataclass(frozen=True)
class _RegisteredTool:
    descriptor: ToolDescriptor
    handler: ToolHandler


class ToolGateway:
    def __init__(self, *, decide: PolicyDecider | None = None) -> None:
        self._registry: dict[str, _RegisteredTool] = {}
        self._decide: PolicyDecider = decide if decide is not None else allow_all

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        if descriptor.name in self._registry:
            raise ValueError(f"tool already registered: {descriptor.name}")
        self._registry[descriptor.name] = _RegisteredTool(descriptor, handler)

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
            result, duration = await self._run_one(call, context)
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
            outcomes[call.call_id] = await self._run_one(call, context)

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
        self, call: ToolCallRequest, context: RunContext
    ) -> tuple[ToolResultBlock, float]:
        started = anyio.current_time()
        tool = self._registry.get(call.tool_name)
        if tool is None:
            error = NormalizedError(
                category=ErrorCategory.UNKNOWN_TOOL,
                reason=f"unknown tool: {call.tool_name}",
            )
            return self._failure(call, error), anyio.current_time() - started

        decision = await self._decide(call, context)
        if decision == "deny":
            error = NormalizedError(
                category=ErrorCategory.POLICY_DENIAL,
                reason=f"call to {call.tool_name} was denied by policy",
            )
            return self._failure(call, error), anyio.current_time() - started

        try:
            outputs = await tool.handler(dict(call.input), context)
        except Exception as exc:
            error = NormalizedError(
                category=ErrorCategory.EXECUTION,
                reason=f"tool execution failed: {exc}",
            )
            return self._failure(call, error), anyio.current_time() - started

        result = ToolResultBlock(
            call_id=call.call_id, outcome="success", outputs=list(outputs)
        )
        return result, anyio.current_time() - started

    @staticmethod
    def _failure(call: ToolCallRequest, error: NormalizedError) -> ToolResultBlock:
        return ToolResultBlock(
            call_id=call.call_id, outcome="failure", outputs=[], error=error
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
