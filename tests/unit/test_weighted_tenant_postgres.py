from __future__ import annotations

import builtins
from collections import Counter
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from loopplane.fairness import PlatformFairnessPolicy, TurnPermitUnavailable
from loopplane.fairness_weighted import (
    WeightedPlatformFairness,
    WeightedTurnPolicy,
    _Request,
    _schedule,
)
from loopplane.fairness_weighted_postgres import WeightedPostgresTurnPermitStore
from tests.weighted_pg_stub import Database

TTL = timedelta(seconds=60)


@pytest.fixture
def database(monkeypatch):
    db = Database()
    monkeypatch.setattr(
        "loopplane.fairness_weighted_postgres._require_psycopg", lambda: db
    )
    return db


def config():
    return WeightedTurnPolicy({"a": 3, "b": 1}, active_cap=1, consecutive_cap=3)


@pytest.mark.anyio
async def test_separate_instances_persist_complete_cycle_shares(database):
    left = WeightedPostgresTurnPermitStore("stub", policy=config())
    right = WeightedPostgresTurnPermitStore("stub", policy=config())

    def seed(book, now):
        for tenant in ["a", "b"]:
            book.waiters.extend(
                _Request(f"{tenant}-{i}", tenant, now + TTL, TTL) for i in range(400)
            )

    await left._mutate(seed)
    starts = []
    for index in range(400):

        def grant(book, now):
            _schedule(book, config(), now)
            permit = next(iter(book.permits.values()))
            del book.permits[permit.permit_id]
            return permit.principal_id

        starts.append(await (left if index % 2 else right)._mutate(grant))
    assert Counter(starts) == {"a": 300, "b": 100}
    assert all(options["connect_timeout"] > 0 for options in database.options)


def test_configuration_mismatch_does_not_replace_existing_state(database):
    WeightedPostgresTurnPermitStore("stub", policy=config())
    original = database.row
    with pytest.raises(ValueError, match="policy"):
        WeightedPostgresTurnPermitStore(
            "stub", policy=WeightedTurnPolicy({"a": 2}, active_cap=1, consecutive_cap=3)
        )
    assert database.row == original


@pytest.mark.anyio
async def test_acquisition_heartbeat_release_and_rollback(database):
    store = WeightedPostgresTurnPermitStore("stub", policy=config())
    permit = await store.take("a", "one", active_cap=1, consecutive_cap=3, ttl=TTL)
    assert await store.heartbeat(permit.permit_id, "one", ttl=TTL)
    assert not await store.heartbeat(permit.permit_id, "wrong", ttl=TTL)
    before = database.row
    database.fail_update = True
    with pytest.raises(TurnPermitUnavailable):
        await store.release(permit.permit_id, "one")
    assert database.row == before
    database.fail_update = False
    await store.release(permit.permit_id, "one")
    assert not await store.heartbeat(permit.permit_id, "one", ttl=TTL)


@pytest.mark.anyio
async def test_expired_permit_is_not_claimed_again(database):
    store = WeightedPostgresTurnPermitStore("stub", policy=config())
    permit = await store.take("a", "one", active_cap=1, consecutive_cap=3, ttl=TTL)

    def expire(book, now):
        from dataclasses import replace

        book.permits[permit.permit_id] = replace(
            permit, expires_at=datetime(2000, 1, 1, tzinfo=UTC)
        )

    await store._mutate(expire)
    replacement = await store.take("a", "one", active_cap=1, consecutive_cap=3, ttl=TTL)
    assert replacement.permit_id != permit.permit_id


def test_safe_construction_error_and_repr(database):
    store = WeightedPostgresTurnPermitStore("private-connection-value", policy=config())
    assert "private-connection-value" not in repr(store)
    database.unavailable = True
    with pytest.raises(TurnPermitUnavailable) as caught:
        WeightedPostgresTurnPermitStore("private-connection-value", policy=config())
    assert "private-connection-value" not in str(caught.value)


def test_driver_value_error_is_redacted(database, monkeypatch):
    from tests.weighted_pg_stub import Connection

    def fail(*args, **kwargs):
        raise ValueError("private-connection-value")

    monkeypatch.setattr(Connection, "execute", fail)
    with pytest.raises(TurnPermitUnavailable) as caught:
        WeightedPostgresTurnPermitStore("stub", policy=config())
    assert "private-connection-value" not in str(caught.value)


@pytest.mark.anyio
async def test_public_turns_across_two_durable_workers(database):
    left = WeightedPostgresTurnPermitStore("stub", policy=config())
    right = WeightedPostgresTurnPermitStore("stub", policy=config())
    workers = [
        WeightedPlatformFairness(PlatformFairnessPolicy(100, 1, 3), turn_permits=s)
        for s in (left, right)
    ]
    blocker = await left.take(
        "blocker", "blocker", active_cap=1, consecutive_cap=3, ttl=TTL
    )
    starts = []

    async def turn(tenant, index):
        async with workers[index % 2].model_turn(tenant):
            starts.append(tenant)

    with anyio.fail_after(15):
        async with anyio.create_task_group() as group:
            for index, tenant in enumerate(["a"] * 30 + ["b"] * 10):
                group.start_soon(turn, tenant, index)
            while await left._mutate(lambda book, now: len(book.waiters)) < 40:
                await anyio.sleep(0.01)
            await left.release(blocker.permit_id, "blocker")
    for prefix in range(4, 41, 4):
        assert Counter(starts[:prefix]) == {"a": prefix * 3 // 4, "b": prefix // 4}


@pytest.mark.anyio
async def test_identity_conflict_does_not_run_the_body(database, monkeypatch):
    store = WeightedPostgresTurnPermitStore("stub", policy=config())
    await store.take("a", "fixed", active_cap=1, consecutive_cap=3, ttl=TTL)
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(100, 1, 3), turn_permits=store
    )

    class _Fixed:
        hex = "fixed"

    monkeypatch.setattr("loopplane.fairness_weighted.uuid.uuid4", lambda: _Fixed())
    calls = 0
    with pytest.raises(ValueError, match="identity"):
        async with fairness.model_turn("b"):
            calls += 1
    assert calls == 0


@pytest.mark.anyio
async def test_driver_outage_runs_an_admitted_turn_locally(database):
    store = WeightedPostgresTurnPermitStore("stub", policy=config())
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(100, 1, 3), turn_permits=store
    )
    database.unavailable = True
    calls = 0
    async with fairness.model_turn("a"):
        calls += 1
    assert calls == 1


@pytest.mark.anyio
async def test_cap_mismatch_is_not_a_store_outage(database):
    store = WeightedPostgresTurnPermitStore("stub", policy=config())
    with pytest.raises(ValueError, match="policy"):
        await store.take("a", "one", active_cap=9, consecutive_cap=3, ttl=TTL)


def test_missing_extra_has_existing_install_hint(monkeypatch):
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        WeightedPostgresTurnPermitStore("stub", policy=config())
