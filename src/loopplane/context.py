"""The Run Context: per-run execution scope handed to tools and policies
(data-model.md; FR-003, FR-113).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio

if TYPE_CHECKING:
    from loopplane.approval.interactions import InteractionBroker


@dataclass
class PlanModeState:
    """Per-run plan-mode flag (spec 038): a minimal mutable holder shared by the
    decide-stage ``plan_mode_policy`` (which reads ``active`` to deny non-read-only
    tools while planning) and the ``exit_plan_mode`` tool (which sets it ``False`` on
    human approval). Created per run and reached through :attr:`RunContext.plan_mode`,
    so it is per-run, never process-global.
    """

    active: bool = True


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
    interactions: InteractionBroker | None = None
    # Per-run plan-mode holder (spec 038); ``None`` means the run is not in plan mode
    # (the plan-mode policy is then a no-op). Shared by reference with the decider and
    # the ``exit_plan_mode`` tool, which both receive this same per-run context.
    plan_mode: PlanModeState | None = None
