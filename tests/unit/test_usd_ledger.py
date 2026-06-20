"""Unit 062: the durable USD ledger (UsdLedger) + its three backends.

A shared parametrized contract over File / SQLite / Postgres-via-stub (offline; no
running DB) asserting the UsdLedger Protocol: add returns the new post-increment total,
get reads it back, an unseen key is Decimal(0), keys are independent, money is exact
Decimal (no float drift), and — the load-bearing case — concurrent same-key adds never
lose an increment. Plus the Postgres import-guard + DSN-not-echoed.
"""

from __future__ import annotations

import builtins
from decimal import Decimal
from pathlib import Path

import anyio
import pytest

from loopplane.ledger import (
    FileUsdLedger,
    PostgresUsdLedger,
    SqliteUsdLedger,
    UsdLedger,
)
from tests import usd_ledger_stub

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["file", "sqlite", "postgres"])
def ledger(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> UsdLedger:
    if request.param == "file":
        return FileUsdLedger(tmp_path)
    if request.param == "postgres":
        pytest.importorskip("psycopg")
        usd_ledger_stub.patch_psycopg(monkeypatch)
        return PostgresUsdLedger(f"postgresql://stub/{tmp_path.name}")
    return SqliteUsdLedger(tmp_path / "ledger.sqlite3")


# --- the shared UsdLedger contract (all three backends) ----------------------


async def test_add_returns_new_total_and_get_reflects_it(ledger: UsdLedger) -> None:
    assert await ledger.add("alice", "2026-06", Decimal("0.10")) == Decimal("0.10")
    assert await ledger.add("alice", "2026-06", Decimal("0.05")) == Decimal("0.15")
    assert ledger.get("alice", "2026-06") == Decimal("0.15")


async def test_get_unseen_is_zero(ledger: UsdLedger) -> None:
    assert ledger.get("nobody", "2026-06") == Decimal(0)


async def test_keys_are_independent(ledger: UsdLedger) -> None:
    await ledger.add("alice", "2026-06", Decimal("1"))
    await ledger.add("alice", "2026-07", Decimal("2"))  # same principal, next month
    await ledger.add("bob", "2026-06", Decimal("3"))  # different principal
    assert ledger.get("alice", "2026-06") == Decimal("1")
    assert ledger.get("alice", "2026-07") == Decimal("2")
    assert ledger.get("bob", "2026-06") == Decimal("3")


async def test_exact_decimal_no_float_drift(ledger: UsdLedger) -> None:
    for _ in range(10):
        await ledger.add("alice", "2026-06", Decimal("0.1"))
    # 0.1 * 10 is exactly 1.0 in Decimal (would drift under float).
    assert ledger.get("alice", "2026-06") == Decimal("1.0")
    big = await ledger.add("alice", "2026-06", Decimal("1234567.89"))
    assert big == Decimal("1234568.89")


async def test_concurrent_adds_never_lose_an_increment(ledger: UsdLedger) -> None:
    # The load-bearing property: 50 concurrent adds to ONE (principal, month) must sum
    # exactly (no lost update). File/SQLite serialize via the per-key lock; the Postgres
    # stub models the DB's atomic upsert.
    async with anyio.create_task_group() as task_group:
        for _ in range(50):
            task_group.start_soon(ledger.add, "alice", "2026-06", Decimal("0.01"))
    assert ledger.get("alice", "2026-06") == Decimal("0.50")


# --- Postgres-specific: import-guard + DSN public-safety ---------------------


def test_postgres_import_guard_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "psycopg":
            raise ImportError("simulated: psycopg not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        PostgresUsdLedger("postgresql://x/db")


def test_dsn_is_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("psycopg")
    usd_ledger_stub.patch_psycopg(monkeypatch)
    dsn = "postgresql://user:do-not-echo-pw@host/db"
    ledger = PostgresUsdLedger(dsn)
    assert "do-not-echo-pw" not in repr(ledger)
    assert "do-not-echo-pw" not in str(ledger)
