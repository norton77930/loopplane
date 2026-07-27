"""The Run Context: per-run execution scope handed to tools and policies
(data-model.md; FR-003, FR-113).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import anyio

if TYPE_CHECKING:
    from loopplane.approval.interactions import InteractionBroker
    from loopplane.tools.background import BackgroundTask
    from loopplane.tools.messaging import Member, Message
    from loopplane.tools.scheduling import Schedule
    from loopplane.tools.worktree import Worktree


@dataclass
class PlanModeState:
    """Per-run plan-mode flag (spec 038): a minimal mutable holder shared by the
    decide-stage ``plan_mode_policy`` (which reads ``active`` to deny non-read-only
    tools while planning) and the ``exit_plan_mode`` tool (which sets it ``False`` on
    human approval). Created per run and reached through :attr:`RunContext.plan_mode`,
    so it is per-run, never process-global.
    """

    active: bool = True


class BackgroundSupervisor(Protocol):
    """The per-run background-task supervisor interface (spec 048; ADR 0002).

    The concrete ``BackgroundTaskSupervisor`` (``loopplane.tools.background``)
    implements it structurally; it is declared here so the controller and
    ``RunContext`` can name it WITHOUT importing the tools layer (Constitution V: the
    controller/loop never import tool sources). The scope owner (the Dispatcher's task
    group / the one-shot ``host.run``) builds a concrete supervisor and stamps it on the
    run's context.
    """

    def create(
        self,
        instruction: str,
        *,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str | None: ...
    def get(self, task_id: str) -> BackgroundTask | None: ...
    def list_tasks(self) -> list[BackgroundTask]: ...
    def stop(self, task_id: str) -> bool: ...
    def cancel_all(self) -> None: ...


# A scope owner builds a supervisor from a task group it owns; typed without the tools
# layer so the controller can reference it (Constitution V).
BackgroundSupervisorFactory = Callable[
    ["anyio.abc.TaskGroup"], "BackgroundSupervisor | None"
]


class ScheduleSupervisor(Protocol):
    """The per-run scheduling supervisor interface (spec 049).

    The concrete ``ScheduleSupervisor`` (``loopplane.tools.scheduling``) implements it
    structurally; declared here so the controller and ``RunContext`` can name it WITHOUT
    importing the tools layer (Constitution V). The scope owner (the Dispatcher's task
    group / the one-shot ``host.run``) builds a concrete supervisor and stamps it on the
    run's context.
    """

    def create(
        self,
        instruction: str,
        *,
        delay_seconds: float | None,
        interval_seconds: float | None,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str | None: ...
    def get(self, schedule_id: str) -> Schedule | None: ...
    def list_schedules(self) -> list[Schedule]: ...
    def cancel(self, schedule_id: str) -> bool: ...
    def cancel_all(self) -> None: ...


ScheduleSupervisorFactory = Callable[
    ["anyio.abc.TaskGroup"], "ScheduleSupervisor | None"
]


class SwarmSupervisor(Protocol):
    """The per-run swarm / agent-to-agent messaging supervisor interface (spec 050;
    ADR 0003).

    The concrete ``SwarmSupervisor`` (``loopplane.tools.messaging``) implements it
    structurally; declared here so the controller and ``RunContext`` can name it WITHOUT
    importing the tools layer (Constitution V). The scope owner (the Dispatcher's task
    group / the one-shot ``host.run``) builds a concrete supervisor and stamps it on the
    run's context. Messages are a SEPARATE in-run registry, NOT runtime events (ADR 0003
    D2), so the Event Bus is unchanged.
    """

    def dispatch(
        self,
        instruction: str,
        *,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
    ) -> str | None: ...
    def get(self, member_id: str) -> Member | None: ...
    def list_members(self) -> list[Member]: ...
    def send(self, from_id: str, to_id: str, content: str) -> str: ...
    def inbox(self, member_id: str) -> list[Message]: ...
    def cancel_all(self) -> None: ...


SwarmSupervisorFactory = Callable[["anyio.abc.TaskGroup"], "SwarmSupervisor | None"]


class WorktreeManager(Protocol):
    """The per-run worktree-isolation manager interface (spec 051).

    The concrete ``WorktreeManager`` (``loopplane.tools.worktree``) implements it
    structurally; declared here so the controller and ``RunContext`` can name it WITHOUT
    importing the tools layer (Constitution V). The scope owner (the Dispatcher / the
    one-shot ``host.run``) builds a concrete manager from the session's working scope,
    stamps it on the run's context; ``cleanup()`` removes the managed worktrees at scope
    exit. No task group — git ops are synchronous.
    """

    async def create(self, *, branch: str | None = None) -> Worktree | str: ...
    def list_worktrees(self) -> list[Worktree]: ...
    async def remove(self, worktree_id: str) -> str | None: ...
    async def cleanup(self) -> None: ...


# A scope owner builds a manager from the session's working scope (NOT a task group —
# worktree ops are synchronous); typed without the tools layer (Constitution V).
WorktreeManagerFactory = Callable[["Path"], "WorktreeManager | None"]


@dataclass
class RunContext:
    session_id: str
    working_scope: Path
    principal_id: str | None = None
    cancellation: anyio.Event = field(default_factory=anyio.Event)
    turn_budget: int | None = None
    session_approval_memory: dict[str, Literal["allow", "deny"]] = field(
        default_factory=dict
    )
    feature_toggles: dict[str, bool] = field(default_factory=dict)
    # Per-run subagent recursion depth (spec 043): ``0`` for a top-level
    # (host-driven) run; a child run spawned by the ``spawn_subagent`` gateway tool
    # carries ``parent.subagent_depth + 1``. The tool compares this against the
    # configured ``max_subagent_depth`` cap and denies a spawn at/over it, so
    # subagents cannot nest without bound. Set only in ``RuntimeController.drive()``
    # (the single ``RunContext`` construction site); per-run, never process-global.
    subagent_depth: int = 0
    interactions: InteractionBroker | None = None
    # Per-run plan-mode holder (spec 038); ``None`` means the run is not in plan mode
    # (the plan-mode policy is then a no-op). Shared by reference with the decider and
    # the ``exit_plan_mode`` tool, which both receive this same per-run context.
    plan_mode: PlanModeState | None = None
    # Optional host-validated browser permission-mode selection (spec 077). ``None``
    # preserves the configured host behavior; a value is per-run metadata consumed by
    # the existing decide-stage policy only and is never checkpointed.
    permission_mode: str | None = None
    # Optional per-run JSON schema for structured output (spec 045); ``None`` means
    # unconstrained. Set only in ``RuntimeController.drive()`` (the single RunContext
    # construction site) from the run request, then forwarded to the assembled
    # ``ModelRequest``. Per-run, never process-global.
    output_schema: dict[str, object] | None = None
    # Per-run background-task supervisor (spec 048; ADR 0002). ``None`` means background
    # tasks are off (the tools return a normalized "not enabled" error). Built by the
    # scope owner (the Dispatcher's task group / the one-shot ``host.run``) and set only
    # in ``RuntimeController.drive()``; per-run.
    background_tasks: BackgroundSupervisor | None = None
    # Per-run scheduling supervisor (spec 049). ``None`` means scheduling is off (the
    # tools return a normalized "not enabled" error). Built by the scope owner (the
    # Dispatcher's task group / the one-shot ``host.run``) and set only in
    # ``RuntimeController.drive()``; per-run.
    schedules: ScheduleSupervisor | None = None
    # Per-run swarm / messaging supervisor (spec 050; ADR 0003). ``None`` = off (the
    # tools return a "not enabled" error). Built by the scope owner, set in ``drive``.
    # Messages are a separate registry, not events (D2).
    swarm: SwarmSupervisor | None = None
    # The caller's member id within a swarm (spec 050); ``None`` = the top-level run
    # (the reserved ``"coordinator"`` id). A member carries its own id, stamped into
    # its child context so its messaging tools resolve "self".
    swarm_member_id: str | None = None
    # Per-run worktree-isolation manager (spec 051). ``None`` means worktrees are off
    # (the tools return a normalized "not enabled" error). Built by the scope owner from
    # the session's working scope; set only in ``RuntimeController.drive()`` (per-run).
    worktrees: WorktreeManager | None = None
