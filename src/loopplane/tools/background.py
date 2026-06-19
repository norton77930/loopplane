"""Background task tools (spec 048; ADR 0002): non-blocking, bounded agent sub-runs.

A ``BackgroundTaskSupervisor`` owns an injected ``anyio`` task group + a per-run task
registry. ``task_create`` launches a bounded child agent run (the unit-043 one-shot
``run_loop`` child, wrapped as an injected ``run_child``) with ``task_group.start_soon``
and returns a task id **immediately** (non-blocking); ``task_get`` / ``task_list`` /
``task_output`` read the registry; ``task_stop`` cancels a running task.

SAFE + additive (ADR 0002): bounded (a count cap + the 043 depth cap), contained (a
failing child → ``failed`` status, never a raise), and lifecycle-bound (pending tasks
are cancelled when the supervisor's scope exits). The supervisor is built by the scope
owner (the Dispatcher's task group; the one-shot ``host.run`` wraps one) and reached via
``RunContext.background_tasks``. Gateway-only (V); child events are captured, never on
the parent bus (VI). Registered only when ``max_background_tasks >= 1`` (0 = off).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio

from loopplane.context import BackgroundSupervisor, RunContext
from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopState,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    max_iterations,
    run_loop,
)
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock

if TYPE_CHECKING:
    from loopplane.host import LoopPlaneHost
    from loopplane.tools.subagent import ChildHostFactory

TaskStatus = Literal["running", "completed", "failed", "stopped"]

# Runs one background child and returns its final text ("" = no usable result).
# Signature: (instruction, allowed_tools, child_depth, working_scope) -> final text.
RunChild = Callable[[str, "tuple[str, ...] | None", int, Path], Awaitable[str]]

_FAILED_MESSAGE = "background task failed"


@dataclass
class BackgroundTask:
    """One background task's registry record (metadata + result; no payloads)."""

    id: str
    status: TaskStatus = "running"
    result: str | None = None
    cancel_scope: anyio.CancelScope = field(default_factory=anyio.CancelScope)


class BackgroundTaskSupervisor:
    """Owns the concurrency scope + registry for one run/session (ADR 0002)."""

    def __init__(
        self,
        *,
        task_group: anyio.abc.TaskGroup,
        run_child: RunChild,
        max_tasks: int,
    ) -> None:
        self._task_group = task_group
        self._run_child = run_child
        self._max_tasks = max_tasks
        self._tasks: dict[str, BackgroundTask] = {}

    def create(
        self,
        instruction: str,
        *,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str | None:
        """Launch a background child run and return its id; ``None`` at the count cap.

        Non-blocking: the child runs via ``task_group.start_soon``; the record is
        ``running`` until the child finishes (``completed`` / ``failed``) or is stopped.
        """

        running = sum(1 for task in self._tasks.values() if task.status == "running")
        if running >= self._max_tasks:
            return None
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = BackgroundTask(id=task_id)
        self._task_group.start_soon(
            self._run, task_id, instruction, allowed_tools, child_depth, working_scope
        )
        return task_id

    async def _run(
        self,
        task_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> None:
        record = self._tasks[task_id]
        with record.cancel_scope:
            try:
                text = await self._run_child(
                    instruction, allowed_tools, child_depth, working_scope
                )
            except Exception:  # noqa: BLE001 - contained: never raise across the Gateway
                record.status = "failed"
                record.result = _FAILED_MESSAGE
                return
            if text:
                record.status = "completed"
                record.result = text
            else:
                record.status = "failed"
                record.result = _FAILED_MESSAGE
            return
        # Reached only when the per-task cancel scope was cancelled (task_stop).
        if record.status == "running":
            record.status = "stopped"

    def get(self, task_id: str) -> BackgroundTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[BackgroundTask]:
        return list(self._tasks.values())

    def stop(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == "running":
            task.cancel_scope.cancel()
            task.status = "stopped"
        return True

    def cancel_all(self) -> None:
        """Cancel every still-running task (called at the run/session scope exit)."""
        for task in self._tasks.values():
            if task.status == "running":
                task.cancel_scope.cancel()
                task.status = "stopped"


def _always_pass(outcome: object, state: LoopState) -> ValidationResult:
    return ValidationResult(status="pass", reason="background task completed")


def _final_assistant_text(history: Sequence[object]) -> str:
    for entry in reversed(list(history)):
        if getattr(entry, "role", None) != "assistant":
            continue
        blocks = getattr(entry, "blocks", ())
        return "".join(
            block.text for block in blocks if isinstance(block, TextBlock)
        ).strip()
    return ""


def make_run_child(build_child_host: ChildHostFactory) -> RunChild:
    """Wrap the unit-043 one-shot ``run_loop`` child into a ``RunChild`` callable.

    Builds a fresh child host (at ``child_depth``, optional ``allowed_tools``, the
    parent's working scope), drives it through the existing ``run_loop`` with NO live
    sink, and returns the child's final assistant text ("" when it did not complete or
    produced no answer). Mirrors ``SpawnSubagentAdapter``, but async-launchable.
    """

    async def run_child(
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str:
        holder: dict[str, LoopPlaneHost] = {}

        def selector() -> LoopPlaneHost:
            host = build_child_host(child_depth, allowed_tools, working_scope)
            holder["host"] = host
            return host

        definition = LoopDefinition(
            loop_id=f"bgtask-{uuid.uuid4().hex}",
            trigger=ManualTrigger(),
            input_source=StaticInput(instruction),
            host_profile=HostRuntimeProfile(selector=selector),
            validation_policy=ValidationPolicy(validator=_always_pass),
            stop_condition=max_iterations(1),
            observation_policy=ObservationPolicy(emit_loop_events=True),
        )
        outcome = await run_loop(definition)
        if outcome.terminal_event != "loop_completed" or outcome.paused:
            return ""
        host = holder.get("host")
        if host is None or not outcome.state.run_refs:
            return ""
        session_id = outcome.state.run_refs[-1].session_id
        try:
            history = host.history_snapshot(session_id)
        except KeyError:
            return ""
        return _final_assistant_text(history)

    return run_child


def make_background_supervisor(
    task_group: anyio.abc.TaskGroup,
    *,
    build_child_host: ChildHostFactory,
    max_tasks: int,
) -> BackgroundTaskSupervisor:
    """Build a supervisor bound to a scope owner's task group (ADR 0002 D3)."""

    return BackgroundTaskSupervisor(
        task_group=task_group,
        run_child=make_run_child(build_child_host),
        max_tasks=max_tasks,
    )


def make_supervisor_factory(
    build_child_host: ChildHostFactory, max_tasks: int
) -> Callable[[anyio.abc.TaskGroup], BackgroundTaskSupervisor]:
    """Bind the child-host factory + count cap into a closure the scope owner calls
    with its own task group (ADR 0002 D3), returned to the host assembly so the
    controller can hold an opaque factory and stay tool-agnostic (Constitution V)."""

    def factory(task_group: anyio.abc.TaskGroup) -> BackgroundTaskSupervisor:
        return make_background_supervisor(
            task_group, build_child_host=build_child_host, max_tasks=max_tasks
        )

    return factory


_DESCRIPTORS = [
    ToolDescriptor(
        name="task_create",
        description=(
            "Launch a background task: a focused child agent run that runs without "
            "blocking this turn. Returns a task id immediately; poll with task_get / "
            "task_output. Pass the work as 'instruction'; optionally restrict tools "
            "with allowed_tools."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["instruction"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="task_get",
        description="Get a background task's status (and result if completed) by id.",
        input_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="task_list",
        description="List this run's background tasks with their statuses.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="task_stop",
        description="Stop (cancel) a running background task by id.",
        input_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="task_output",
        description=(
            "Get a background task's output: its final result if completed, else its "
            "current status."
        ),
        input_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
]


def _coerce_allowed_tools(raw: object) -> tuple[str, ...] | None:
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    return None


class BackgroundTasksAdapter:
    """A Tool Gateway adapter exposing the five background-task tools (spec 048).

    Stateless: the per-run state lives in the ``BackgroundTaskSupervisor`` reached via
    ``RunContext.background_tasks``. Holds ``max_subagent_depth`` for the 043 depth cap
    (a background task is a child run at ``subagent_depth + 1``).
    """

    def __init__(self, *, max_subagent_depth: int) -> None:
        self._max_subagent_depth = max_subagent_depth

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(_DESCRIPTORS)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        supervisor = context.background_tasks
        if supervisor is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message="background tasks are not enabled for this run",
            )
            return
        if name == "task_create":
            async for output in self._create(call_input, context, supervisor):
                yield output
            return
        if name == "task_list":
            tasks = supervisor.list_tasks()
            if not tasks:
                yield TextBlock(text="no background tasks")
                return
            lines = [f"{task.id}: {task.status}" for task in tasks]
            yield TextBlock(text="\n".join(lines))
            return
        task_id = str(call_input["task_id"])
        if name == "task_stop":
            if not supervisor.stop(task_id):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"unknown task id: {task_id}",
                )
                return
            task = supervisor.get(task_id)
            status = task.status if task is not None else "stopped"
            yield TextBlock(text=f"task {task_id}: {status}")
            return
        task = supervisor.get(task_id)
        if task is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION, message=f"unknown task id: {task_id}"
            )
            return
        if name == "task_output":
            if task.status == "completed" and task.result is not None:
                yield TextBlock(text=task.result)
            else:
                yield TextBlock(text=f"task {task_id}: {task.status}")
            return
        # task_get
        summary = f"task {task_id}: {task.status}"
        if task.status in ("completed", "failed") and task.result is not None:
            summary += f"\n{task.result}"
        yield TextBlock(text=summary)

    async def _create(
        self,
        call_input: dict[str, object],
        context: RunContext,
        supervisor: BackgroundSupervisor,
    ) -> AsyncIterator[AdapterOutput]:
        if context.subagent_depth >= self._max_subagent_depth:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message=(
                    f"background task depth cap reached "
                    f"({self._max_subagent_depth}); refusing to launch a task"
                ),
            )
            return
        instruction = str(call_input["instruction"])
        allowed_tools = _coerce_allowed_tools(call_input.get("allowed_tools"))
        task_id = supervisor.create(
            instruction,
            allowed_tools=allowed_tools,
            child_depth=context.subagent_depth + 1,
            working_scope=context.working_scope,
        )
        if task_id is None:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message="background task count cap reached; refusing to launch a task",
            )
            return
        yield TextBlock(text=f"background task started: {task_id}")

    async def shutdown(self) -> None:
        return None
