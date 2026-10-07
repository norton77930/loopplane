from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from loopplane.fairness import PlatformFairnessPolicy, TurnPermitUnavailable
from loopplane.fairness_weighted import (
    WeightedInMemoryTurnPermitStore,
    WeightedPlatformFairness,
    WeightedTurnPolicy,
    _Book,
    _Request,
    _schedule,
)

NOW = datetime(2026, 9, 7, tzinfo=UTC)
TTL = timedelta(seconds=60)


def policy(weights: dict[str, int], cap: int = 100) -> WeightedTurnPolicy:
    return WeightedTurnPolicy(weights, active_cap=1, consecutive_cap=cap)


def burst(weights: dict[str, int], count: int, cap: int = 100) -> list[str]:
    book = _Book()
    for tenant in weights:
        for index in range(count):
            book.waiters.append(_Request(f"{tenant}-{index}", tenant, NOW + TTL, TTL))
    starts = []
    for _ in range(count):
        _schedule(book, policy(weights, cap), NOW)
        grant = next(iter(book.permits.values()))
        starts.append(grant.principal_id)
        del book.permits[grant.permit_id]
    return starts


@pytest.mark.parametrize(
    "weights,count,expected",
    [
        ({"a": 3, "b": 1}, 400, {"a": 300, "b": 100}),
        ({"a": 3, "b": 1, "c": 1}, 500, {"a": 300, "b": 100, "c": 100}),
        ({"a": 100, "b": 1}, 101, {"a": 100, "b": 1}),
    ],
)
def test_complete_cycles_allocate_tenant_shares(weights, count, expected):
    assert Counter(burst(weights, count)) == expected


def test_hard_consecutive_cap_wins_over_weight():
    starts = burst({"a": 3, "b": 1}, 400, cap=1)
    assert Counter(starts) == {"a": 200, "b": 200}
    assert all(a != b for a, b in zip(starts, starts[1:], strict=False))


def test_queue_depth_does_not_multiply_weight_and_fifo_is_preserved():
    book = _Book()
    for tenant, count in [("a", 100), ("b", 10)]:
        book.waiters.extend(
            _Request(f"{tenant}-{i}", tenant, NOW + TTL, TTL) for i in range(count)
        )
    holders = []
    for _ in range(20):
        _schedule(book, policy({"a": 1, "b": 1}), NOW)
        permit = next(iter(book.permits.values()))
        holders.append(permit.holder_id)
        book.permits.clear()
    assert [h for h in holders if h.startswith("a-")] == [f"a-{i}" for i in range(10)]
    assert [h for h in holders if h.startswith("b-")] == [f"b-{i}" for i in range(10)]


def test_polling_full_capacity_never_changes_entitlement():
    book = _Book(
        waiters=[
            _Request("a1", "a", NOW + TTL, TTL),
            _Request("b1", "b", NOW + TTL, TTL),
        ]
    )
    config = policy({"a": 3, "b": 1})
    _schedule(book, config, NOW)
    scores = dict(book.scores)
    for _ in range(100):
        _schedule(book, config, NOW)
    assert book.scores == scores
    assert len(book.permits) == 1


def test_idle_tenants_do_not_keep_credit_and_expiry_reclaims_capacity():
    book = _Book(waiters=[_Request("a1", "a", NOW + TTL, TTL)], scores={"idle": 999})
    config = policy({"a": 3, "idle": 100})
    _schedule(book, config, NOW)
    assert "idle" not in book.scores
    book.waiters.append(_Request("b1", "b", NOW + 2 * TTL, TTL))
    _schedule(book, config, NOW + TTL)
    assert [p.principal_id for p in book.permits.values()] == ["b"]


@pytest.mark.parametrize("weight", [True, False, 0, -1, 1.5, 101, "3"])
def test_invalid_weights_fail_without_echo(weight):
    with pytest.raises(ValueError, match="weight") as caught:
        policy({"private-tenant": weight})
    assert "private-tenant" not in str(caught.value)


def test_policy_copies_mapping_and_redacts_it():
    weights = {"private-tenant": 3}
    config = policy(weights)
    weights["private-tenant"] = 99
    assert config.weights["private-tenant"] == 3
    with pytest.raises(TypeError):
        config.weights["private-tenant"] = 4
    assert "private-tenant" not in repr(config)


@pytest.mark.anyio
async def test_store_grants_distinct_permits_and_rejects_policy_mismatch():
    config = WeightedTurnPolicy({"a": 3}, active_cap=2, consecutive_cap=3)
    store = WeightedInMemoryTurnPermitStore(config)
    left = await store.take("a", "left", active_cap=2, consecutive_cap=3, ttl=TTL)
    right = await store.take("a", "right", active_cap=2, consecutive_cap=3, ttl=TTL)
    assert left.permit_id != right.permit_id
    assert not await store.heartbeat(left.permit_id, "wrong", ttl=TTL)
    await store.release(left.permit_id, "left")
    assert not await store.heartbeat(left.permit_id, "left", ttl=TTL)
    with pytest.raises(ValueError, match="policy"):
        await store.take("a", "third", active_cap=1, consecutive_cap=3, ttl=TTL)


@pytest.mark.anyio
async def test_cancelled_pending_request_is_removed():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 3, "b": 1}))
    first = await store.take("a", "first", active_cap=1, consecutive_cap=100, ttl=TTL)
    with anyio.move_on_after(0.05) as scope:
        await store.take("b", "cancelled", active_cap=1, consecutive_cap=100, ttl=TTL)
    assert scope.cancel_called
    await store.release(first.permit_id, "first")
    with anyio.fail_after(1):
        next_permit = await store.take(
            "c", "next", active_cap=1, consecutive_cap=100, ttl=TTL
        )
    assert next_permit.principal_id == "c"


@pytest.mark.anyio
@pytest.mark.parametrize("workers", [1, 2])
async def test_weighted_fairness_exposes_all_tenants_before_local_gate(workers):
    store = WeightedInMemoryTurnPermitStore(policy({"a": 3, "b": 1}, cap=3))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(100, 1, 3), turn_permits=store
    )
    peer = WeightedPlatformFairness(
        PlatformFairnessPolicy(100, 1, 3), turn_permits=store
    )
    blocker = await store.take(
        "blocker", "blocker", active_cap=1, consecutive_cap=3, ttl=TTL
    )
    starts = []

    async def turn(tenant, index):
        worker = peer if workers == 2 and index % 2 else fairness
        async with worker.model_turn(tenant):
            starts.append(tenant)

    with anyio.fail_after(5):
        async with anyio.create_task_group() as group:
            for index, tenant in enumerate(["a"] * 12 + ["b"] * 4):
                group.start_soon(turn, tenant, index)
            while len(store._book.waiters) < 16:
                await anyio.sleep(0)
            await store.release(blocker.permit_id, "blocker")
    assert Counter(starts[:12]) == {"a": 9, "b": 3}


@pytest.mark.anyio
async def test_rejected_holder_collision_does_not_steal_existing_grant():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1}))
    permit = await store.take("a", "same", active_cap=1, consecutive_cap=100, ttl=TTL)
    with pytest.raises(ValueError, match="identity"):
        await store.take("b", "same", active_cap=1, consecutive_cap=100, ttl=TTL)
    assert await store.heartbeat(permit.permit_id, "same", ttl=TTL)


@pytest.mark.anyio
@pytest.mark.parametrize("outage", [False, True])
async def test_local_active_cap_and_model_runs_once(monkeypatch, outage):
    config = WeightedTurnPolicy({"a": 3}, active_cap=2, consecutive_cap=3)
    store = WeightedInMemoryTurnPermitStore(config)

    async def unavailable(*args, **kwargs):
        raise TurnPermitUnavailable("unavailable")

    if outage:
        monkeypatch.setattr(store, "take", unavailable)
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 2, 3), turn_permits=store
    )
    active = 0
    peak = 0
    calls = []
    release = anyio.Event()
    two_started = anyio.Event()

    async def turn(index):
        nonlocal active, peak
        async with fairness.model_turn(str(index)):
            active += 1
            peak = max(peak, active)
            calls.append(index)
            if len(calls) == 2:
                two_started.set()
            await release.wait()
            active -= 1

    with anyio.fail_after(3):
        async with anyio.create_task_group() as group:
            for index in range(3):
                group.start_soon(turn, index)
            await two_started.wait()
            await anyio.sleep(0.05)
            assert len(calls) == 2
            release.set()
    assert sorted(calls) == [0, 1, 2]
    assert peak == 2


def test_fairness_rejects_mismatched_local_caps():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1}))
    with pytest.raises(ValueError, match="policy"):
        WeightedPlatformFairness(PlatformFairnessPolicy(1, 2, 100), turn_permits=store)


@pytest.mark.anyio
async def test_heartbeat_keeps_long_running_turn_live(monkeypatch):
    monkeypatch.setattr("loopplane.fairness_weighted._TTL", timedelta(seconds=0.15))
    store = WeightedInMemoryTurnPermitStore(policy({"a": 3, "b": 1}))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    first_started = anyio.Event()
    release = anyio.Event()
    second_started = anyio.Event()

    async def first():
        async with fairness.model_turn("a"):
            first_started.set()
            await release.wait()

    async def second():
        async with fairness.model_turn("b"):
            second_started.set()

    with anyio.fail_after(3):
        async with anyio.create_task_group() as group:
            group.start_soon(first)
            await first_started.wait()
            group.start_soon(second)
            await anyio.sleep(0.35)
            assert not second_started.is_set()
            release.set()
        assert second_started.is_set()


@pytest.mark.anyio
async def test_cancelled_admission_releases_outstanding_capacity():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1}))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(1, 1, 100), turn_permits=store
    )
    with anyio.move_on_after(0.02):
        async with fairness.admit("a"):
            await anyio.sleep_forever()
    async with fairness.admit("a"):
        assert fairness.max_outstanding_per_tenant == 1


@pytest.mark.anyio
async def test_model_body_error_is_not_reinterpreted_as_acquisition_failure():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1}))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    calls = 0
    with pytest.raises(TurnPermitUnavailable, match="application"):
        async with fairness.model_turn("a"):
            calls += 1
            raise TurnPermitUnavailable("application")
    assert calls == 1
    assert not store._book.permits


@pytest.mark.anyio
async def test_cancellation_releases_held_permit():
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1}))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    with anyio.move_on_after(0.05):
        async with fairness.model_turn("a"):
            await anyio.sleep_forever()
    assert not store._book.permits
    with anyio.fail_after(1):
        async with fairness.model_turn("b"):
            pass


@pytest.mark.anyio
async def test_identity_conflict_does_not_run_the_body(monkeypatch):
    store = WeightedInMemoryTurnPermitStore(policy({"a": 1, "b": 1}))
    await store.take("a", "fixed", active_cap=1, consecutive_cap=100, ttl=TTL)
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )

    class _Fixed:
        hex = "fixed"

    monkeypatch.setattr("loopplane.fairness_weighted.uuid.uuid4", lambda: _Fixed())
    calls = 0
    with pytest.raises(ValueError, match="identity"):
        async with fairness.model_turn("b"):
            calls += 1
    assert calls == 0


class _DownOnce(WeightedInMemoryTurnPermitStore):
    """First acquire fails; later acquires use the real store."""

    def __init__(self, config: WeightedTurnPolicy) -> None:
        super().__init__(config)
        self._failed = False

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ):
        if not self._failed:
            self._failed = True
            raise TurnPermitUnavailable("down")
        return await super().take(
            principal_id,
            holder_id,
            active_cap=active_cap,
            consecutive_cap=consecutive_cap,
            ttl=ttl,
        )


@pytest.mark.anyio
async def test_local_wait_does_not_hold_the_shared_slot():
    store = _DownOnce(policy({"a": 1, "b": 1}))
    fairness = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    first_inside = anyio.Event()
    release = anyio.Event()
    second_inside = anyio.Event()

    async def first() -> None:
        async with fairness.model_turn("a"):
            first_inside.set()
            await release.wait()

    async def second() -> None:
        async with fairness.model_turn("b"):
            second_inside.set()

    with anyio.fail_after(3):
        async with anyio.create_task_group() as group:
            group.start_soon(first)
            await first_inside.wait()
            group.start_soon(second)
            for _ in range(20):
                await anyio.sleep(0.01)
            assert not second_inside.is_set()
            assert all(
                permit.principal_id != "b" for permit in store._book.permits.values()
            )
            release.set()
            await second_inside.wait()


class _BlipOnce(WeightedInMemoryTurnPermitStore):
    """Real in-memory store whose next renewal raises a connectivity blip."""

    def __init__(self, config: WeightedTurnPolicy) -> None:
        super().__init__(config)
        self.fail_renewal = False

    async def heartbeat(
        self, permit_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool:
        if self.fail_renewal:
            self.fail_renewal = False
            raise TurnPermitUnavailable("blip")
        return await super().heartbeat(permit_id, holder_id, ttl=ttl)


@pytest.mark.anyio
async def test_failed_renewal_ends_body_before_the_other_worker(monkeypatch):
    monkeypatch.setattr("loopplane.fairness_weighted._TTL", timedelta(seconds=0.15))
    store = _BlipOnce(policy({"a": 1, "b": 1}))
    left = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    right = WeightedPlatformFairness(
        PlatformFairnessPolicy(10, 1, 100), turn_permits=store
    )
    inside = 0
    peak = 0
    order: list[str] = []
    first_inside = anyio.Event()
    second_inside = anyio.Event()

    async def turn(worker: WeightedPlatformFairness, tenant: str, name: str) -> None:
        nonlocal inside, peak
        try:
            async with worker.model_turn(tenant):
                inside += 1
                peak = max(peak, inside)
                order.append(f"enter-{name}")
                try:
                    if name == "first":
                        first_inside.set()
                        await anyio.sleep_forever()
                    else:
                        second_inside.set()
                finally:
                    inside -= 1
                    order.append(f"leave-{name}")
        except Exception:
            order.append(f"err-{name}")

    with anyio.fail_after(3):
        async with anyio.create_task_group() as group:
            group.start_soon(turn, left, "a", "first")
            await first_inside.wait()
            store.fail_renewal = True
            group.start_soon(turn, right, "b", "second")
            await second_inside.wait()
            group.cancel_scope.cancel()

    assert peak == 1
    assert order.index("leave-first") < order.index("enter-second")
    later = await store.take(
        "c", "later", active_cap=1, consecutive_cap=100, ttl=timedelta(seconds=1)
    )
    assert later.principal_id == "c"
