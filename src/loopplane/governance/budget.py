"""Budget, cost, and quota policies (contracts/policies.md; FR-040-FR-050).

Stateful deciders that bound a loop's spend and per-tool call counts. State is
in-process per decider instance (persistent state reserved). A denied call
consumes neither budget nor quota.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loopplane.governance.base import allow, deny

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor


@dataclass(frozen=True)
class CostModel:
    """Deterministic per-tool cost weights with a default (FR-041)."""

    weights: Mapping[str, int]
    default: int = 1

    def cost(self, tool_name: str) -> int:
        return self.weights.get(tool_name, self.default)


class _BudgetDecider:
    """A stateful decider that denies once the next call's cost would exceed the
    ceiling; the running ``spent`` is inspectable (FR-040, FR-041)."""

    def __init__(self, ceiling: int, cost_model: CostModel) -> None:
        self._ceiling = ceiling
        self._cost_model = cost_model
        self.spent = 0

    async def __call__(
        self,
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        cost = self._cost_model.cost(call.tool_name)
        if self.spent + cost > self._ceiling:
            return deny(f"budget policy: ceiling {self._ceiling} would be exceeded")
        self.spent += cost
        return allow()


class _QuotaDecider:
    """A stateful decider that denies a tool once its per-tool call limit is
    reached (FR-050)."""

    def __init__(self, limits: Mapping[str, int]) -> None:
        self._limits = dict(limits)
        self._counts: dict[str, int] = {}

    async def __call__(
        self,
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        name = call.tool_name
        limit = self._limits.get(name)
        if limit is not None and self._counts.get(name, 0) >= limit:
            return deny(f"quota policy: tool {name!r} reached its limit {limit}")
        self._counts[name] = self._counts.get(name, 0) + 1
        return allow()


def budget_policy(
    ceiling: int, *, cost_model: CostModel | None = None
) -> PolicyDecider:
    return _BudgetDecider(
        ceiling, cost_model if cost_model is not None else CostModel({})
    )


def quota_policy(limits: Mapping[str, int]) -> PolicyDecider:
    return _QuotaDecider(limits)
