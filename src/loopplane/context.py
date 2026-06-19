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


@dataclass
class RunContext:
    session_id: str
    working_scope: Path
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
