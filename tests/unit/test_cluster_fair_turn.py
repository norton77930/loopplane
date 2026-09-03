"""Unit 086: cluster-wide fair model-turn permits (ADR 0021)."""

from __future__ import annotations

import builtins
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import pytest

from loopplane.fairness import (
    InMemoryTurnPermitStore,
    PlatformFairness,
    PlatformFairnessPolicy,
    TurnPermit,
    TurnPermitUnavailable,
)

pytestmark = pytest.mark.anyio


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 3, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _policy(
    *,
    max_active_model_calls: int = 1,
    max_consecutive_starts: int = 1,
) -> PlatformFairnessPolicy:
    return PlatformFairnessPolicy(
        max_outstanding_per_tenant=4,
        max_active_model_calls=max_active_model_calls,
        max_consecutive_starts=max_consecutive_starts,
    )


def _pair(
    store: InMemoryTurnPermitStore,
    *,
    max_active_model_calls: int = 1,
    max_consecutive_starts: int = 1,
) -> tuple[PlatformFairness, PlatformFairness]:
    policy = _policy(
        max_active_model_calls=max_active_model_calls,
        max_consecutive_starts=max_consecutive_starts,
    )
    return (
        PlatformFairness(policy, turn_permits=store),
        PlatformFairness(policy, turn_permits=store),
    )


async def _wait_for(predicate: object, timeout: float = 2.0) -> None:
    with anyio.fail_after(timeout):
        while not predicate():  # type: ignore[operator]
            await anyio.lowlevel.checkpoint()


def test_platform_fairness_constructs_without_turn_permits() -> None:
    fairness = PlatformFairness(_policy())
    assert fairness.model_turn("alice") is not None


def test_store_and_fairness_repr_are_public_safe() -> None:
    store = InMemoryTurnPermitStore()
    fairness = PlatformFairness(_policy(), turn_permits=store)
    assert (
        "permit" not in repr(store).lower()
        or repr(store) == "InMemoryTurnPermitStore()"
    )
    assert "alice" not in repr(fairness)
    assert "alice" not in str(store)


async def test_two_workers_both_ready_principals_obtain_a_start() -> None:
    store = InMemoryTurnPermitStore()
    left, right = _pair(store)
    started: list[str] = []
    alice_release = anyio.Event()
    bob_release = anyio.Event()
    alice2_release = anyio.Event()

    async def hold(fairness: PlatformFairness, tenant: str, gate: anyio.Event) -> None:
        async with fairness.model_turn(tenant):
            started.append(tenant)
            await gate.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(hold, left, "alice", alice_release)
        await _wait_for(lambda: started == ["alice"])
        tg.start_soon(hold, left, "alice", alice2_release)
        tg.start_soon(hold, right, "bob", bob_release)
        await anyio.lowlevel.checkpoint()
        alice_release.set()
        await _wait_for(lambda: len(started) >= 2)
        assert started[1] == "bob"
        bob_release.set()
        await _wait_for(lambda: len(started) == 3)
        assert started == ["alice", "bob", "alice"]
        alice2_release.set()


async def test_single_ready_principal_is_not_blocked() -> None:
    store = InMemoryTurnPermitStore()
    left, _right = _pair(store)
    with anyio.fail_after(1):
        async with left.model_turn("alice"):
            pass
        async with left.model_turn("alice"):
            pass


async def test_active_cap_two_allows_overlapping_principals() -> None:
    store = InMemoryTurnPermitStore()
    left, right = _pair(store, max_active_model_calls=2)
    started: list[str] = []
    alice_gate = anyio.Event()
    bob_gate = anyio.Event()

    async def hold(fairness: PlatformFairness, tenant: str, gate: anyio.Event) -> None:
        async with fairness.model_turn(tenant):
            started.append(tenant)
            await gate.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(hold, left, "alice", alice_gate)
        tg.start_soon(hold, right, "bob", bob_gate)
        await _wait_for(lambda: set(started) == {"alice", "bob"})
        alice_gate.set()
        bob_gate.set()


async def test_active_cap_one_waits_without_stealing() -> None:
    store = InMemoryTurnPermitStore()
    left, right = _pair(store, max_active_model_calls=1)
    started: list[str] = []
    alice_gate = anyio.Event()
    bob_gate = anyio.Event()

    async def hold(fairness: PlatformFairness, tenant: str, gate: anyio.Event) -> None:
        async with fairness.model_turn(tenant):
            started.append(tenant)
            await gate.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(hold, left, "alice", alice_gate)
        await _wait_for(lambda: started == ["alice"])
        tg.start_soon(hold, right, "bob", bob_gate)
        await anyio.sleep(0.05)
        assert started == ["alice"]
        alice_gate.set()
        await _wait_for(lambda: started == ["alice", "bob"])
        bob_gate.set()


async def test_store_error_degrades_to_local_scheduler() -> None:
    class _Boom:
        async def take(self, *args: object, **kwargs: object) -> TurnPermit:
            raise TurnPermitUnavailable("store unavailable")

        async def heartbeat(self, *args: object, **kwargs: object) -> bool:
            return False

        async def release(self, *args: object, **kwargs: object) -> None:
            return None

    fairness = PlatformFairness(_policy(), turn_permits=_Boom())  # type: ignore[arg-type]
    with anyio.fail_after(1):
        async with fairness.model_turn("alice"):
            pass


async def test_programming_error_on_take_is_not_degraded() -> None:
    class _Broken:
        async def take(self, *args: object, **kwargs: object) -> TurnPermit:
            raise TypeError("bug in store.take")

        async def heartbeat(self, *args: object, **kwargs: object) -> bool:
            return False

        async def release(self, *args: object, **kwargs: object) -> None:
            return None

    fairness = PlatformFairness(_policy(), turn_permits=_Broken())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bug in store.take"):
        async with fairness.model_turn("alice"):
            pass


async def test_expired_permit_allows_a_later_take() -> None:
    clock = _Clock()
    store = InMemoryTurnPermitStore(clock=clock)
    first = await store.take(
        "alice",
        "w1",
        active_cap=1,
        consecutive_cap=1,
        ttl=timedelta(seconds=1),
    )
    clock.now = clock.now + timedelta(seconds=2)
    second = await store.take(
        "alice",
        "w2",
        active_cap=1,
        consecutive_cap=1,
        ttl=timedelta(seconds=1),
    )
    assert second.permit_id != first.permit_id
    assert second.holder_id == "w2"


async def test_released_permit_cannot_be_heartbeated_back() -> None:
    store = InMemoryTurnPermitStore()
    permit = await store.take(
        "alice",
        "w1",
        active_cap=1,
        consecutive_cap=1,
        ttl=timedelta(seconds=30),
    )
    await store.release(permit.permit_id, "w1")
    assert (
        await store.heartbeat(permit.permit_id, "w1", ttl=timedelta(seconds=30))
        is False
    )
    second = await store.take(
        "alice",
        "w2",
        active_cap=1,
        consecutive_cap=1,
        ttl=timedelta(seconds=30),
    )
    assert second.holder_id == "w2"


async def test_postgres_two_workers_both_ready_principals_obtain_a_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("psycopg")
    from loopplane.fairness_postgres import PostgresTurnPermitStore
    from tests import fairness_pg_stub

    fairness_pg_stub.patch_psycopg(monkeypatch)
    store = PostgresTurnPermitStore(f"postgresql://stub/{tmp_path}-fair")
    policy = _policy()
    left = PlatformFairness(policy, turn_permits=store)
    right = PlatformFairness(policy, turn_permits=store)
    started: list[str] = []
    alice_release = anyio.Event()
    bob_release = anyio.Event()
    alice2_release = anyio.Event()

    async def hold(fairness: PlatformFairness, tenant: str, gate: anyio.Event) -> None:
        async with fairness.model_turn(tenant):
            started.append(tenant)
            await gate.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(hold, left, "alice", alice_release)
        await _wait_for(lambda: started == ["alice"])
        tg.start_soon(hold, left, "alice", alice2_release)
        tg.start_soon(hold, right, "bob", bob_release)
        await anyio.lowlevel.checkpoint()
        alice_release.set()
        await _wait_for(lambda: len(started) >= 2)
        assert started[1] == "bob"
        bob_release.set()
        await _wait_for(lambda: len(started) == 3)
        assert started == ["alice", "bob", "alice"]
        alice2_release.set()


async def test_postgres_store_take_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("psycopg")
    from loopplane.fairness_postgres import PostgresTurnPermitStore
    from tests import fairness_pg_stub

    fairness_pg_stub.patch_psycopg(monkeypatch)
    store = PostgresTurnPermitStore(f"postgresql://stub/{tmp_path}")
    left = await store.take(
        "alice", "w1", active_cap=1, consecutive_cap=1, ttl=timedelta(seconds=30)
    )
    await store.release(left.permit_id, "w1")
    right = await store.take(
        "alice", "w2", active_cap=1, consecutive_cap=1, ttl=timedelta(seconds=30)
    )
    assert right.holder_id == "w2"


def test_postgres_dsn_is_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("psycopg")
    from loopplane.fairness_postgres import PostgresTurnPermitStore
    from tests import fairness_pg_stub

    fairness_pg_stub.patch_psycopg(monkeypatch)
    dsn = "postgresql://user:do-not-echo-pw@host/db"
    store = PostgresTurnPermitStore(dsn)
    assert "do-not-echo-pw" not in repr(store)
    assert "do-not-echo-pw" not in str(store)


def test_postgres_requires_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "psycopg":
            raise ImportError("simulated: psycopg not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from loopplane.fairness_postgres import PostgresTurnPermitStore

    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        PostgresTurnPermitStore("postgresql://x/db")
