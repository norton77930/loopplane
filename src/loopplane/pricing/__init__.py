"""Server-side pricing (spec 053; gap G21, Phase A): pure token-usage → USD cost.

A host-supplied :class:`PricingTable` maps a model id to its per-token USD rates; its
:meth:`PricingTable.cost` returns the **exact** :class:`decimal.Decimal` USD cost of a
:class:`loopplane.model.TokenUsage` record, or ``None`` for a model it has no price for.

**Pure metadata**: pricing enforces nothing, makes no network call, and ships no prices
— the loop and gateway never import it. A host or observability layer calls
:meth:`PricingTable.cost` on demand, and (since spec 055) ``loopplane.budget`` reuses
it to enforce USD caps; pricing itself stays byte-identical and unenforcing. USD budget
caps / enforcement (G22 Phase B) build on it in :mod:`loopplane.budget` (spec 055; ADR
0005), default-off so the runtime is byte-identical when no caps are configured.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from loopplane.model.boundary import TokenUsage

__all__ = ["PricingRate", "PricingTable"]


@dataclass(frozen=True)
class PricingRate:
    """A model's per-token USD rates (exact decimals; input + output)."""

    input_rate: Decimal
    output_rate: Decimal


@dataclass(frozen=True)
class PricingTable:
    """A host-supplied, immutable mapping of model id → :class:`PricingRate` (spec 053).

    The runtime ships no prices: the host constructs the table from its own rate data.
    """

    rates: Mapping[str, PricingRate]

    def cost(self, usage: TokenUsage, model: str) -> Decimal | None:
        """The exact USD cost of ``usage`` under ``model``'s rate, or ``None`` when the
        model has no price (never a guessed value, never a crash).

        ``cost = input_tokens × input_rate + output_tokens × output_rate`` (exact).
        """

        rate = self.rates.get(model)
        if rate is None:
            return None
        return (
            usage.input_tokens * rate.input_rate
            + usage.output_tokens * rate.output_rate
        )
