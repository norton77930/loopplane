"""USD budget enforcement (spec 055; gap G22 Phase B; ADR 0005).

Builds on 053's pure pricing (``loopplane.pricing``) to enforce per-message /
per-session USD caps INSIDE the Agent Loop turn cycle — the only place ``TokenUsage``
exists (on ``TurnEnd``). A :class:`BudgetChecker` accumulates a run's USD cost from each
turn's usage and reports when a cap is crossed; the loop then terminates with the
``budget-exceeded`` reason after the crossing turn (USD is knowable only post-turn, so
spend is bounded to ≈ cap + one turn, never pre-empted).

**Default-off**: with no caps configured no ``BudgetChecker`` is built, the loop's
optional collaborator stays ``None``, and the runtime is byte-identical. **Fail-soft**:
an unpriced model (``PricingTable.cost`` → ``None``) is NOT enforced for that turn (a
diagnostic is emitted), never a crash or a guessed price. Exact
:class:`decimal.Decimal` money. The durable per-user-monthly ledger (Phase C) is
deferred (ADR 0005 D7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from loopplane.model.boundary import TokenUsage
from loopplane.pricing import PricingTable

__all__ = ["UsdBudgetCaps", "BudgetChecker"]


@dataclass(frozen=True)
class UsdBudgetCaps:
    """The USD caps for a run/session (each ``None`` = that dimension is off)."""

    per_message_usd: Decimal | None = None
    per_session_usd: Decimal | None = None

    def any_set(self) -> bool:
        return self.per_message_usd is not None or self.per_session_usd is not None


@dataclass
class BudgetChecker:
    """Per-session USD accumulator + cap test (ADR 0005).

    Built once per session-assembly and carried by the Agent Loop; the per-message total
    resets each run (:meth:`start_run`) while the per-session total persists across runs
    (and resets only when the session is rebuilt on resume).
    """

    caps: UsdBudgetCaps
    pricing: PricingTable
    model_id: str
    _message_spent: Decimal = field(default=Decimal(0), init=False)
    _session_spent: Decimal = field(default=Decimal(0), init=False)
    _unpriced: bool = field(default=False, init=False)

    def start_run(self) -> None:
        """Reset the per-message accumulator; the per-session total persists."""
        self._message_spent = Decimal(0)

    def record_turn(self, usage: TokenUsage) -> Decimal | None:
        """Add this turn's USD cost to the per-message + per-session totals.

        The cost is ``input × input_rate + output × output_rate`` (053). Returns the
        turn's cost, or ``None`` (fail-soft) when the model has no price — in which case
        nothing is accumulated.
        """
        cost = self.pricing.cost(usage, self.model_id)
        if cost is None:
            self._unpriced = True
            return None
        self._unpriced = False
        self._message_spent += cost
        self._session_spent += cost
        return cost

    def exceeded(self) -> bool:
        """Whether a configured per-message OR per-session USD cap is now crossed."""
        if (
            self.caps.per_message_usd is not None
            and self._message_spent > self.caps.per_message_usd
        ):
            return True
        return (
            self.caps.per_session_usd is not None
            and self._session_spent > self.caps.per_session_usd
        )

    @property
    def spent(self) -> Decimal:
        """The current run's accumulated USD."""
        return self._message_spent

    @property
    def unpriced(self) -> bool:
        """Whether the most recent recorded turn had no price (fail-soft)."""
        return self._unpriced
