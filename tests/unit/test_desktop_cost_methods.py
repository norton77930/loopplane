"""Desktop sidecar cost projection (083 Wave 1, T001/T002).

``cost.get`` must carry the unpriced / partially-priced / unavailable / zero
distinction inside the projection (from ``agent_controls().budget.pricing``),
preserve exact ``Decimal`` strings, and never leak a path, exception, or
principal identifier (FR-001, FR-002, FR-012, FR-018; SC-001, SC-004).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from methods.cost import CostMethods  # noqa: E402
from methods.inspection import InspectionMethods  # noqa: E402
from protocol import RpcError  # noqa: E402

pytestmark = pytest.mark.anyio

_PRICING_STATES = {"priced", "partially_unpriced", "unpriced", "unknown"}


class _FakeHost:
    """Duck-typed host exposing only the public methods CostMethods reads."""

    def __init__(
        self,
        *,
        session_cost: Decimal | None = None,
        session_cost_error: bool = False,
        pricing: Any = "unknown",
        agent_controls_error: bool = False,
        monthly: Decimal | None = None,
        monthly_error: bool = False,
        sessions: tuple[tuple[str, str | None], ...] = (),
    ) -> None:
        self._session_cost = session_cost
        self._session_cost_error = session_cost_error
        self._pricing = pricing
        self._agent_controls_error = agent_controls_error
        self._monthly = monthly
        self._monthly_error = monthly_error
        self._sessions = sessions

    def list_sessions(self) -> tuple[Any, ...]:
        return tuple(
            SimpleNamespace(session_id=sid, principal_id=pid)
            for sid, pid in self._sessions
        )

    def session_cost(self, session_id: str) -> Decimal | None:
        if self._session_cost_error:
            raise RuntimeError(r"tracker exploded at C:\private\profile\tracker.db")
        return self._session_cost

    def agent_controls(self, session_id: str) -> Any:
        if self._agent_controls_error:
            raise RuntimeError("/etc/secret/budget raised KeyError('token')")
        return SimpleNamespace(
            budget=SimpleNamespace(pricing=self._pricing, tracking="available")
        )

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        if self._monthly_error:
            raise RuntimeError("ledger backend failure at /var/secret/usd.sqlite")
        return self._monthly


def _methods(host: _FakeHost, principal: str | None = "principal-1") -> CostMethods:
    return CostMethods(host, principal_provider=lambda: principal)  # type: ignore[arg-type]


async def test_priced_session_preserves_exact_decimal_strings() -> None:
    host = _FakeHost(
        session_cost=Decimal("0.123456"),
        pricing="priced",
        monthly=Decimal("12.50"),
        sessions=(("s-1", "principal-1"),),
    )
    result = await _methods(host).cost_get({"session_id": "s-1"})
    assert result["session"] == {"status": "priced", "usd": "0.123456"}
    assert result["monthly"] == {"status": "available", "usd": "12.50"}


async def test_four_session_states_are_distinct() -> None:
    partially = await _methods(
        _FakeHost(
            session_cost=Decimal("0.10"),
            pricing="partially_unpriced",
            sessions=(("s-1", "principal-1"),),
        )
    ).cost_get({"session_id": "s-1"})
    unpriced = await _methods(
        _FakeHost(
            session_cost=Decimal("0"),
            pricing="unpriced",
            sessions=(("s-1", "principal-1"),),
        )
    ).cost_get({"session_id": "s-1"})
    zero_priced = await _methods(
        _FakeHost(
            session_cost=Decimal("0"),
            pricing="priced",
            sessions=(("s-1", "principal-1"),),
        )
    ).cost_get({"session_id": "s-1"})
    unavailable = await _methods(
        _FakeHost(session_cost=None, sessions=(("s-1", "principal-1"),))
    ).cost_get({"session_id": "s-1"})

    assert partially["session"] == {"status": "partially_unpriced", "usd": "0.10"}
    assert unpriced["session"] == {"status": "unpriced", "usd": "0"}
    assert zero_priced["session"] == {"status": "priced", "usd": "0"}
    assert unavailable["session"] == {"status": "unavailable", "usd": None}
    views = [
        (v["session"]["status"], v["session"]["usd"])
        for v in (partially, unpriced, zero_priced, unavailable)
    ]
    assert len(set(views)) == 4


async def test_unconfigured_host_answers_unavailable_never_zero() -> None:
    host = _FakeHost(
        session_cost=None, monthly=None, sessions=(("s-1", "principal-1"),)
    )
    result = await _methods(host).cost_get({"session_id": "s-1"})
    assert result["session"] == {"status": "unavailable", "usd": None}
    assert result["monthly"] == {"status": "unavailable", "usd": None}


async def test_monthly_without_principal_is_unavailable() -> None:
    host = _FakeHost(monthly=Decimal("5"))
    result = await _methods(host, principal=None).cost_get({})
    assert result["monthly"] == {"status": "unavailable", "usd": None}


async def test_missing_session_id_still_answers_monthly() -> None:
    host = _FakeHost(monthly=Decimal("3.007"))
    result = await _methods(host).cost_get({})
    assert result["session"] == {"status": "unavailable", "usd": None}
    assert result["monthly"] == {"status": "available", "usd": "3.007"}


async def test_unowned_or_unknown_session_is_not_found() -> None:
    host = _FakeHost(
        session_cost=Decimal("1"),
        pricing="priced",
        sessions=(("s-1", "someone-else"),),
    )
    with pytest.raises(RpcError) as exc:
        await _methods(host).cost_get({"session_id": "s-1"})
    assert exc.value.category == "not_found"
    with pytest.raises(RpcError) as unknown:
        await _methods(host).cost_get({"session_id": "s-404"})
    assert unknown.value.category == "not_found"


async def test_non_string_session_id_is_invalid_params() -> None:
    with pytest.raises(RpcError) as exc:
        await _methods(_FakeHost()).cost_get({"session_id": 42})
    assert exc.value.category == "invalid_params"


async def test_host_failures_become_absence_without_markers() -> None:
    host = _FakeHost(
        session_cost_error=True,
        agent_controls_error=True,
        monthly_error=True,
        sessions=(("s-1", "principal-1"),),
    )
    result = await _methods(host).cost_get({"session_id": "s-1"})
    assert result["session"] == {"status": "unavailable", "usd": None}
    assert result["monthly"] == {"status": "unavailable", "usd": None}
    blob = str(result).lower()
    for marker in ("private", "secret", "sqlite", "exploded", "keyerror", "\\", "/"):
        assert marker not in blob
    assert "principal-1" not in str(result)


async def test_unexpected_pricing_vocabulary_is_clamped_to_unknown() -> None:
    host = _FakeHost(
        session_cost=Decimal("2"),
        pricing="DROP TABLE pricing",
        sessions=(("s-1", "principal-1"),),
    )
    result = await _methods(host).cost_get({"session_id": "s-1"})
    assert result["session"]["status"] == "unknown"
    assert result["session"]["status"] in _PRICING_STATES


async def test_capabilities_list_cost_card_unavailable_without_ledger() -> None:
    inspection = InspectionMethods(
        _FakeHost(monthly=None),  # type: ignore[arg-type]
        principal_provider=lambda: "principal-1",
    )
    listed = await inspection.capabilities_list({})
    card = next(c for c in listed["capabilities"] if c["id"] == "cost")
    assert card["available"] is False
    assert card["status"] == "unavailable"
    assert isinstance(card["reason"], str) and card["reason"]


async def test_capabilities_list_cost_card_available_with_ledger() -> None:
    inspection = InspectionMethods(
        _FakeHost(monthly=Decimal("7.25")),  # type: ignore[arg-type]
        principal_provider=lambda: "principal-1",
    )
    listed = await inspection.capabilities_list({})
    card = next(c for c in listed["capabilities"] if c["id"] == "cost")
    assert card["available"] is True
    assert card["status"] == "available"
    assert card["reason"] is None
