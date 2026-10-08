"""Agent scheduling tools (spec 049): deferred + recurring bounded agent sub-runs.

A ``ScheduleSupervisor`` owns an injected ``anyio`` task group + a per-run schedule
registry. ``schedule_create`` starts a timer task (in the task group) that waits via
an injectable :class:`Sleeper` and then fires a bounded child agent run (the
unit-043/048 one-shot ``run_loop`` child) — once for a delay, each period for an
interval — returning a schedule id **immediately** (non-blocking). ``schedule_get`` /
``schedule_list`` read the registry; ``schedule_cancel`` stops further firings.

SAFE + additive: reuses the unit-048 supervisor pattern (ADR 0002 — in-run concurrent
child runs) + the unit-004 interval concept; the only new mechanism is the timer + an
injectable ``Sleeper`` (so interval tests are deterministic with NO real sleeping;
unit-004's ``Clock`` is left unchanged). Bounded (a count cap + the 043 depth cap),
contained (a failing occurrence is recorded, never raised), and lifecycle-bound (timers
are cancelled when the supervisor's scope exits — the scope owner calls ``cancel_all``
so an infinite interval timer never hangs a one-shot run). Reached via
``RunContext.schedules``. Gateway-only (V); child events are captured, never on the
parent bus (VI). Registered only when ``max_schedules >= 1`` (0 = off, byte-identical).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import anyio

from loopplane.context import RunContext, SubagentFanout
from loopplane.context import ScheduleSupervisor as _ScheduleSupervisorProto
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.tools.background import RunChild, make_run_child

if TYPE_CHECKING:
    from loopplane.tools.subagent import ChildHostFactory

ScheduleStatus = Literal["active", "completed", "cancelled"]

_FAILED_MESSAGE = "scheduled task failed"


class Sleeper(Protocol):
    """An async "wait this long" seam so interval timing is deterministic in tests."""

    async def sleep(self, seconds: float) -> None: ...


class AnyioSleeper:
    """The production sleeper: real time via ``anyio.sleep``."""

    async def sleep(self, seconds: float) -> None:
        await anyio.sleep(seconds)


@dataclass
class Schedule:
    """One schedule's registry record (metadata + last result; no payloads)."""

    id: str
    cadence: str
    status: ScheduleStatus = "active"
    occurrences: int = 0
    last_result: str | None = None
    cancel_scope: anyio.CancelScope = field(default_factory=anyio.CancelScope)


class ScheduleSupervisor:
    """Owns the timer scope + registry for one run/session (reuses ADR 0002)."""

    def __init__(
        self,
        *,
        task_group: anyio.abc.TaskGroup,
        run_child: RunChild,
        max_schedules: int,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._task_group = task_group
        self._run_child = run_child
        self._max_schedules = max_schedules
        self._sleeper: Sleeper = sleeper or AnyioSleeper()
        self._schedules: dict[str, Schedule] = {}

    def create(
        self,
        instruction: str,
        *,
        delay_seconds: float | None,
        interval_seconds: float | None,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None = None,
    ) -> str | None:
        """Register a schedule + start its timer; ``None`` at the count cap.

        Assumes the adapter has validated exactly one positive cadence. Non-blocking:
        the timer runs via ``task_group.start_soon``. ``fanout`` is the spawn
        counter captured at admit time.
        """

        active = sum(1 for s in self._schedules.values() if s.status == "active")
        if active >= self._max_schedules:
            return None
        schedule_id = uuid.uuid4().hex
        if interval_seconds is not None:
            self._schedules[schedule_id] = Schedule(
                id=schedule_id, cadence=f"interval:{interval_seconds}"
            )
            self._task_group.start_soon(
                self._run_interval,
                schedule_id,
                instruction,
                allowed_tools,
                float(interval_seconds),
                child_depth,
                working_scope,
                fanout,
            )
        else:
            assert delay_seconds is not None
            self._schedules[schedule_id] = Schedule(
                id=schedule_id, cadence=f"delay:{delay_seconds}"
            )
            self._task_group.start_soon(
                self._run_delay,
                schedule_id,
                instruction,
                allowed_tools,
                float(delay_seconds),
                child_depth,
                working_scope,
                fanout,
            )
        return schedule_id

    async def _run_delay(
        self,
        schedule_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        delay: float,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None,
    ) -> None:
        record = self._schedules[schedule_id]
        with record.cancel_scope:
            await self._sleeper.sleep(delay)
            await self._fire_once(
                record,
                instruction,
                allowed_tools,
                child_depth,
                working_scope,
                fanout,
            )
            record.status = "completed"
            return
        # Reached only when the per-schedule scope was cancelled (cancel / cancel_all).
        if record.status == "active":
            record.status = "cancelled"

    async def _run_interval(
        self,
        schedule_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        interval: float,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None,
    ) -> None:
        record = self._schedules[schedule_id]
        with record.cancel_scope:
            while True:
                await self._sleeper.sleep(interval)
                await self._fire_once(
                    record,
                    instruction,
                    allowed_tools,
                    child_depth,
                    working_scope,
                    fanout,
                )
        # Reached only on cancellation — an interval loop never ends on its own.
        if record.status == "active":
            record.status = "cancelled"

    async def _fire_once(
        self,
        record: Schedule,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None,
    ) -> None:
        try:
            text = await self._run_child(
                instruction, allowed_tools, child_depth, working_scope, fanout
            )
        except Exception:  # noqa: BLE001 - contained: never raise across the Gateway
            record.occurrences += 1
            record.last_result = _FAILED_MESSAGE
            return
        record.occurrences += 1
        record.last_result = text or _FAILED_MESSAGE

    def get(self, schedule_id: str) -> Schedule | None:
        return self._schedules.get(schedule_id)

    def list_schedules(self) -> list[Schedule]:
        return list(self._schedules.values())

    def cancel(self, schedule_id: str) -> bool:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return False
        if schedule.status == "active":
            schedule.cancel_scope.cancel()
            schedule.status = "cancelled"
        return True

    def cancel_all(self) -> None:
        """Cancel every active schedule's timer (called at the run/session scope exit,
        so an infinite interval timer never hangs the task group)."""
        for schedule in self._schedules.values():
            if schedule.status == "active":
                schedule.cancel_scope.cancel()
                schedule.status = "cancelled"


def make_schedule_supervisor(
    task_group: anyio.abc.TaskGroup,
    *,
    build_child_host: ChildHostFactory,
    max_schedules: int,
    sleeper: Sleeper | None = None,
) -> ScheduleSupervisor:
    """Build a supervisor bound to a scope owner's task group."""

    return ScheduleSupervisor(
        task_group=task_group,
        run_child=make_run_child(build_child_host),
        max_schedules=max_schedules,
        sleeper=sleeper,
    )


def make_schedule_supervisor_factory(
    build_child_host: ChildHostFactory, max_schedules: int
) -> Callable[[anyio.abc.TaskGroup], ScheduleSupervisor]:
    """Bind the child-host factory + count cap into a closure the scope owner calls
    with its own task group, returned to the host assembly so the controller can hold
    an opaque factory and stay tool-agnostic (Constitution V)."""

    def factory(task_group: anyio.abc.TaskGroup) -> ScheduleSupervisor:
        return make_schedule_supervisor(
            task_group, build_child_host=build_child_host, max_schedules=max_schedules
        )

    return factory


_DESCRIPTORS = [
    ToolDescriptor(
        name="schedule_create",
        description=(
            "Schedule a focused child agent run to fire after a delay or on a "
            "recurring interval (provide exactly one of delay_seconds / "
            "interval_seconds, a positive number). Returns a schedule id immediately; "
            "inspect with schedule_get / schedule_list, stop with schedule_cancel. "
            "Pass the work as 'instruction'; optional allowed_tools restricts tools."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "delay_seconds": {"type": "number"},
                "interval_seconds": {"type": "number"},
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["instruction"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="schedule_get",
        description="Get a schedule's cadence, status, and occurrence count by id.",
        input_schema={
            "type": "object",
            "properties": {"schedule_id": {"type": "string"}},
            "required": ["schedule_id"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="schedule_list",
        description="List this run's schedules with their cadence and status.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="schedule_cancel",
        description="Cancel a schedule by id (stops any further firings).",
        input_schema={
            "type": "object",
            "properties": {"schedule_id": {"type": "string"}},
            "required": ["schedule_id"],
            "additionalProperties": False,
        },
    ),
]


def _coerce_allowed_tools(raw: object) -> tuple[str, ...] | None:
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    return None


def _coerce_positive(raw: object) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and raw > 0:
        return float(raw)
    return None


class SchedulingToolsAdapter:
    """A Tool Gateway adapter exposing the four scheduling tools (spec 049).

    Stateless: the per-run state lives in the ``ScheduleSupervisor`` reached via
    ``RunContext.schedules``. Holds ``max_subagent_depth`` for the 043 depth cap (a
    scheduled occurrence is a child run at ``subagent_depth + 1``).
    """

    def __init__(self, *, max_subagent_depth: int) -> None:
        self._max_subagent_depth = max_subagent_depth

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(_DESCRIPTORS)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        supervisor = context.schedules
        if supervisor is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message="scheduling is not enabled for this run",
            )
            return
        if name == "schedule_create":
            async for output in self._create(call_input, context, supervisor):
                yield output
            return
        if name == "schedule_list":
            schedules = supervisor.list_schedules()
            if not schedules:
                yield TextBlock(text="no schedules")
                return
            lines = [f"{s.id}: {s.status} ({s.cadence})" for s in schedules]
            yield TextBlock(text="\n".join(lines))
            return
        schedule_id = str(call_input["schedule_id"])
        if name == "schedule_cancel":
            if not supervisor.cancel(schedule_id):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"unknown schedule id: {schedule_id}",
                )
                return
            schedule = supervisor.get(schedule_id)
            status = schedule.status if schedule is not None else "cancelled"
            yield TextBlock(text=f"schedule {schedule_id}: {status}")
            return
        # schedule_get
        schedule = supervisor.get(schedule_id)
        if schedule is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"unknown schedule id: {schedule_id}",
            )
            return
        summary = (
            f"schedule {schedule_id}: {schedule.status} "
            f"(cadence {schedule.cadence}, {schedule.occurrences} run(s))"
        )
        if schedule.last_result is not None:
            summary += f"\nlast: {schedule.last_result}"
        yield TextBlock(text=summary)

    async def _create(
        self,
        call_input: dict[str, object],
        context: RunContext,
        supervisor: _ScheduleSupervisorProto,
    ) -> AsyncIterator[AdapterOutput]:
        if context.subagent_depth >= self._max_subagent_depth:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message=(
                    f"schedule depth cap reached "
                    f"({self._max_subagent_depth}); refusing to schedule"
                ),
            )
            return
        delay = _coerce_positive(call_input.get("delay_seconds"))
        interval = _coerce_positive(call_input.get("interval_seconds"))
        if (delay is None) == (interval is None):
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    "provide exactly one of delay_seconds / interval_seconds "
                    "(a positive number)"
                ),
            )
            return
        instruction = str(call_input["instruction"])
        allowed_tools = _coerce_allowed_tools(call_input.get("allowed_tools"))
        schedule_id = supervisor.create(
            instruction,
            delay_seconds=delay,
            interval_seconds=interval,
            allowed_tools=allowed_tools,
            child_depth=context.subagent_depth + 1,
            working_scope=context.working_scope,
            fanout=context.subagent_fanout,
        )
        if schedule_id is None:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message="schedule count cap reached; refusing to schedule",
            )
            return
        yield TextBlock(text=f"schedule started: {schedule_id}")

    async def shutdown(self) -> None:
        return None
