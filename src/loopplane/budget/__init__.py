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

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from loopplane.ledger import UsdLedger
from loopplane.model.boundary import TokenUsage
from loopplane.pricing import PricingTable

__all__ = ["UsdBudgetCaps", "BudgetChecker"]


def _utc_month_now() -> str:
    """The current UTC calendar month as a ``YYYY-MM`` string (063; ADR 0010)."""
    return datetime.now(UTC).strftime("%Y-%m")


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
    pre_turn_max_output_tokens: int | None = None
    # 063 (G22 Phase C; ADR 0010) — the OPTIONAL durable per-user-monthly dimension.
    # When ``ledger`` + ``principal_id`` + ``per_user_monthly_usd`` are ALL set,
    # ``record_turn`` (async) adds this turn's cost to the ``(principal_id, month)``
    # ledger and folds the returned monthly total into ``exceeded()``; ``month`` is a
    # caller-injectable ``YYYY-MM`` provider (default UTC now). All unset → no ledger
    # await → byte-identical to 055. ``loopplane.ledger`` is foundational (not tools).
    ledger: UsdLedger | None = None
    principal_id: str | None = None
    per_user_monthly_usd: Decimal | None = None
    month: Callable[[], str] = _utc_month_now
    _message_spent: Decimal = field(default=Decimal(0), init=False)
    _session_spent: Decimal = field(default=Decimal(0), init=False)
    _monthly_total: Decimal = field(default=Decimal(0), init=False)
    _unpriced: bool = field(default=False, init=False)
    _ledger_unavailable: bool = field(default=False, init=False)

    def _monthly_active(self) -> bool:
        return (
            self.ledger is not None
            and self.principal_id is not None
            and self.per_user_monthly_usd is not None
        )

    def start_run(self) -> None:
        """Reset the per-message accumulator; the per-session total persists."""
        self._message_spent = Decimal(0)

    def pre_turn_enabled(self) -> bool:
        """Whether enough local state exists to run a pre-turn estimate."""
        return self.pre_turn_max_output_tokens is not None and self.caps.any_set()

    def pre_turn_exceeded(self, estimated_input_tokens: int) -> bool:
        """Whether the next estimated turn would exceed a known in-memory cap.

        This is non-mutating and fail-open: without a configured max-output estimate,
        active per-message/per-session cap, or price for the model, it returns False.
        """
        if not self.pre_turn_enabled():
            return False
        cost = self.pricing.cost(
            TokenUsage(
                input_tokens=estimated_input_tokens,
                output_tokens=self.pre_turn_max_output_tokens,
            ),
            self.model_id,
        )
        if cost is None:
            return False
        if (
            self.caps.per_message_usd is not None
            and self._message_spent + cost > self.caps.per_message_usd
        ):
            return True
        return (
            self.caps.per_session_usd is not None
            and self._session_spent + cost > self.caps.per_session_usd
        )

    async def record_turn(self, usage: TokenUsage) -> Decimal | None:
        """Add this turn's USD cost to the per-message + per-session totals (and, when
        the monthly dimension is configured, to the durable per-user-monthly ledger).

        The cost is ``input × input_rate + output × output_rate`` (053). Returns the
        turn's cost, or ``None`` (fail-soft) when the model has no price — in which case
        nothing is accumulated. The monthly ledger ``add`` is **fail-open** (063; ADR
        0010 D9): a ledger outage sets :attr:`ledger_unavailable` and skips the monthly
        accumulation for that turn — never a crash, never a denial. With no monthly
        dimension this awaits nothing new (byte-identical to 055).
        """
        cost = self.pricing.cost(usage, self.model_id)
        if cost is None:
            self._unpriced = True
            return None
        self._unpriced = False
        self._message_spent += cost
        self._session_spent += cost
        if self._monthly_active():
            assert self.ledger is not None and self.principal_id is not None
            try:
                self._monthly_total = await self.ledger.add(
                    self.principal_id, self.month(), cost
                )
                self._ledger_unavailable = False
            except Exception:
                # FAIL-OPEN: a ledger outage must not crash or deny the run; the monthly
                # cap is simply not enforced for this turn (a public-safe diagnostic is
                # emitted by the loop).
                self._ledger_unavailable = True
        return cost

    def exceeded(self) -> bool:
        """Whether a configured per-message, per-session, OR per-user-monthly USD cap is
        now crossed."""
        if (
            self.caps.per_message_usd is not None
            and self._message_spent > self.caps.per_message_usd
        ):
            return True
        if (
            self.caps.per_session_usd is not None
            and self._session_spent > self.caps.per_session_usd
        ):
            return True
        return (
            self.per_user_monthly_usd is not None
            and self._monthly_total > self.per_user_monthly_usd
        )

    @property
    def spent(self) -> Decimal:
        """The current run's accumulated USD."""
        return self._message_spent

    @property
    def session_spent(self) -> Decimal:
        """The session's accumulated USD across runs (read-only; 064 cost surfacing)."""
        return self._session_spent

    @property
    def unpriced(self) -> bool:
        """Whether the most recent recorded turn had no price (fail-soft)."""
        return self._unpriced

    @property
    def ledger_unavailable(self) -> bool:
        """Whether the most recent recorded turn could not reach the durable monthly
        ledger (063; fail-open — the monthly cap was not enforced that turn)."""
        return self._ledger_unavailable
