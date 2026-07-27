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
from loopplane.gateway.sizing import measure_outputs, reduce_outputs
from loopplane.gateway.spi import AdapterOutput, ErrorOutput, ToolAdapter
from loopplane.gateway.validation import validate_input
from loopplane.hooks.decisions import ToolGateDeny, ToolGateModify
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    AfterToolFailurePayload,
    AfterToolUsePayload,
    BeforeToolUsePayload,
    FileChangedPayload,
    LifecyclePoint,
)
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor
from loopplane.model.content import OutputBlock, TextBlock, ToolResultBlock

ToolHandler = Callable[
    [dict[str, object], RunContext], Awaitable[Sequence[OutputBlock]]
]

ArtifactHandoff = Callable[
    [ToolCallRequest, list[OutputBlock], RunContext],
    Awaitable[tuple[str, str]],
]
"""Persists oversized outputs in full; returns (stable reference, preview)."""

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


class _ManagedAdapterEntry:
    __slots__ = (
        "adapter",
        "closed",
        "leases",
        "retired",
        "shutdown_started",
        "tools",
    )

    def __init__(self, adapter: ToolAdapter) -> None:
        self.adapter = adapter
        self.closed = anyio.Event()
        self.leases = 0
        self.retired = False
        self.shutdown_started = False
        self.tools: dict[str, _RegisteredTool] = {}


class _RegisteredTool:
    __slots__ = ("adapter", "descriptor", "managed")

    def __init__(
        self,
        descriptor: ToolDescriptor,
        adapter: ToolAdapter,
        *,
        managed: _ManagedAdapterEntry | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.adapter = adapter
        self.managed = managed


class ToolGateway:
    def __init__(
        self,
        *,
        decide: PolicyDecider | None = None,
        call_timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
        artifact_handoff: ArtifactHandoff | None = None,
        hooks: HookDispatcher | None = None,
    ) -> None:
        # The per-call time limit is always enforced; pass a large value for
        # an effectively unbounded call rather than disabling it outright.
        self._registry: dict[str, _RegisteredTool] = {}
        self._scoped_adapters: dict[tuple[str, str], _ManagedAdapterEntry] = {}
        self._scoped_registry: dict[str, dict[str, _RegisteredTool]] = {}
        self._decide: PolicyDecider = decide if decide is not None else allow_all
        self._call_timeout_seconds = call_timeout_seconds
        self._output_limit_bytes = output_limit_bytes
        self._artifact_handoff = artifact_handoff
        # Optional lifecycle hooks (feature 015). Absent by default: when None,
        # every stage below runs its existing path with no added work (FR-011).
        self._hooks = hooks

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        self._add(descriptor, _HandlerAdapter(descriptor, handler))

    def register_adapter(self, adapter: ToolAdapter) -> None:
        for descriptor in adapter.describe():
            self._add(descriptor, adapter)

    def _add(self, descriptor: ToolDescriptor, adapter: ToolAdapter) -> None:
        if descriptor.name in self._registry:
            raise ValueError(f"tool already registered: {descriptor.name}")
        if any(
            descriptor.name in registry for registry in self._scoped_registry.values()
        ):
            raise ValueError(
                f"tool already registered in a scoped registry: {descriptor.name}"
            )
        self._registry[descriptor.name] = _RegisteredTool(descriptor, adapter)

    def descriptors(self, principal_id: str | None = None) -> list[ToolDescriptor]:
        descriptors = [tool.descriptor for tool in self._registry.values()]
        if principal_id is not None:
            descriptors.extend(
                tool.descriptor
                for tool in self._scoped_registry.get(principal_id, {}).values()
            )
        return descriptors

    def is_concurrency_safe(
        self, tool_name: str, principal_id: str | None = None
    ) -> bool:
        tool = self._find_tool(tool_name, principal_id)
        if tool is None:
            return False
        return tool.descriptor.concurrency_safe

    async def replace_scoped_adapter(
        self,
        principal_id: str,
        adapter_id: str,
        adapter: ToolAdapter,
    ) -> None:
        if not principal_id or not adapter_id:
            raise ValueError("principal_id and adapter_id are required")
        descriptors = tuple(adapter.describe())
        names = [descriptor.name for descriptor in descriptors]
        if len(names) != len(set(names)):
            raise ValueError("scoped adapter exposes duplicate tool names")

        key = (principal_id, adapter_id)
        previous = self._scoped_adapters.get(key)
        if previous is not None and previous.adapter is adapter:
            return
        owner_registry = self._scoped_registry.setdefault(principal_id, {})
        for name in names:
            if name in self._registry:
                raise ValueError(f"tool conflicts with shared registry: {name}")
            existing = owner_registry.get(name)
            if existing is not None and existing.managed is not previous:
                raise ValueError(f"tool already registered for principal: {name}")

        candidate = _ManagedAdapterEntry(adapter)
        for descriptor in descriptors:
            candidate.tools[descriptor.name] = _RegisteredTool(
                descriptor, adapter, managed=candidate
            )

        if previous is not None:
            for name, registered in previous.tools.items():
                if owner_registry.get(name) is registered:
                    owner_registry.pop(name)
        owner_registry.update(candidate.tools)
        self._scoped_adapters[key] = candidate

        if previous is not None and self._retire(previous):
            await self._shutdown_entry(previous)

    async def remove_scoped_adapter(self, principal_id: str, adapter_id: str) -> None:
        entry = self._scoped_adapters.pop((principal_id, adapter_id), None)
        if entry is None:
            return
        owner_registry = self._scoped_registry.get(principal_id)
        if owner_registry is not None:
            for name, registered in entry.tools.items():
                if owner_registry.get(name) is registered:
                    owner_registry.pop(name)
            if not owner_registry:
                self._scoped_registry.pop(principal_id, None)
        if self._retire(entry):
            await self._shutdown_entry(entry)

    async def shutdown_scoped_adapters(self) -> None:
        entries = list(self._scoped_adapters.values())
        self._scoped_adapters.clear()
        self._scoped_registry.clear()
        immediate = [entry for entry in entries if self._retire(entry)]
        for entry in immediate:
            await self._shutdown_entry(entry)
        for entry in entries:
            await entry.closed.wait()

    def _find_tool(
        self, tool_name: str, principal_id: str | None
    ) -> _RegisteredTool | None:
        shared = self._registry.get(tool_name)
        if shared is not None:
            return shared
        if principal_id is None:
            return None
        return self._scoped_registry.get(principal_id, {}).get(tool_name)

    def _resolve_and_lease(
        self, tool_name: str, principal_id: str | None
    ) -> _RegisteredTool | None:
        tool = self._find_tool(tool_name, principal_id)
        if tool is not None and tool.managed is not None:
            tool.managed.leases += 1
        return tool

    @staticmethod
    def _retire(entry: _ManagedAdapterEntry) -> bool:
        entry.retired = True
        if entry.leases == 0 and not entry.shutdown_started:
            entry.shutdown_started = True
            return True
        return False

    async def _release_entry(self, entry: _ManagedAdapterEntry) -> None:
        entry.leases -= 1
        if entry.leases < 0:
            raise RuntimeError("managed adapter lease underflow")
        if entry.retired and entry.leases == 0 and not entry.shutdown_started:
            entry.shutdown_started = True
            await self._shutdown_entry(entry)

    @staticmethod
    async def _shutdown_entry(entry: _ManagedAdapterEntry) -> None:
        try:
            with anyio.CancelScope(shield=True):
                await entry.adapter.shutdown()
        except Exception:
            pass
        finally:
            entry.closed.set()

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

        # Stage 1: resolve (FR-021). Scoped resolution and the lease increment
        # are one non-yielding operation, so replacement cannot close the
        # selected adapter before this call releases it.
        tool = self._resolve_and_lease(call.tool_name, context.principal_id)
        if tool is None:
            return self._failure(
                call,
                NormalizedError(
                    category=ErrorCategory.UNKNOWN_TOOL,
                    reason=f"unknown tool: {call.tool_name}",
                ),
            ), anyio.current_time() - started

        managed = tool.managed
        try:
            return await self._run_registered(call, context, emitter, tool, started)
        finally:
            if managed is not None:
                await self._release_entry(managed)

    async def _run_registered(
        self,
        call: ToolCallRequest,
        context: RunContext,
        emitter: EventEmitter,
        tool: _RegisteredTool,
        started: float,
    ) -> tuple[ToolResultBlock, float]:
        def elapsed() -> float:
            return anyio.current_time() - started

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

        # Stage 3b: before-tool hooks (feature 015) — fire only on the allow path,
        # after approval, so a hook can deny or modify but never widen what
        # approval allowed (FR-009, FR-012). A deny reuses the policy-denial path;
        # a modify replaces the inputs and is re-validated before execution.
        effective_input = dict(call.input)
        if self._hooks is not None:
            decision = await self._hooks.decide_tool(
                BeforeToolUsePayload(
                    session_id=context.session_id,
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    input=dict(effective_input),
                )
            )
            if isinstance(decision, ToolGateDeny):
                return self._failure(
                    call,
                    NormalizedError(
                        category=ErrorCategory.POLICY_DENIAL, reason=decision.reason
                    ),
                ), elapsed()
            if isinstance(decision, ToolGateModify):
                problem = validate_input(tool.descriptor.input_schema, decision.input)
                if problem is not None:
                    return self._failure(
                        call,
                        NormalizedError(
                            category=ErrorCategory.VALIDATION, reason=problem
                        ),
                    ), elapsed()
                effective_input = dict(decision.input)

        # Stages 4–6: execute under the per-call time limit; normalize every
        # failure (FR-024, FR-025).
        outputs: list[OutputBlock] = []
        error: NormalizedError | None = None
        timed_out = False
        try:
            with anyio.move_on_after(self._call_timeout_seconds) as scope:
                async for output in tool.adapter.invoke(
                    call.tool_name, dict(effective_input), context
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
            if self._hooks is not None:
                await self._hooks.fire(
                    LifecyclePoint.after_tool_failure,
                    AfterToolFailurePayload(
                        session_id=context.session_id,
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        error_category=error.category.value,
                        reason=error.reason,
                    ),
                )
            return self._failure(call, error, outputs), elapsed()

        # Stage 7: size-manage (FR-026). With artifact storage attached the
        # full output is preserved and the result carries preview + reference
        # (FR-090, FR-091); otherwise reduction is bounded truncation.
        artifact_reference: str | None = None
        if measure_outputs(outputs) > self._output_limit_bytes:
            if self._artifact_handoff is not None:
                artifact_reference, preview = await self._artifact_handoff(
                    call, outputs, context
                )
                outputs = [TextBlock(text=preview)]
            else:
                outputs = reduce_outputs(outputs, self._output_limit_bytes)
        result = ToolResultBlock(
            call_id=call.call_id,
            outcome="success",
            outputs=outputs,
            artifact_reference=artifact_reference,
        )
        if self._hooks is not None:
            await self._hooks.fire(
                LifecyclePoint.after_tool_use,
                AfterToolUsePayload(
                    session_id=context.session_id,
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    duration_seconds=elapsed(),
                ),
            )
            # file-changed: a successful non-read-only tool that names a path
            # (FR-013). Read-only tools and tools without a path never fire it.
            if not tool.descriptor.read_only:
                changed = effective_input.get("path") or effective_input.get(
                    "file_path"
                )
                if isinstance(changed, str) and changed:
                    await self._hooks.fire(
                        LifecyclePoint.file_changed,
                        FileChangedPayload(
                            session_id=context.session_id,
                            call_id=call.call_id,
                            tool_name=call.tool_name,
                            path=changed,
                        ),
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
            artifact_reference=result.artifact_reference,
        )
