"""Unit 072: in-process platform fairness scheduler and quota."""

from __future__ import annotations

from dataclasses import dataclass

import anyio
import pytest

from loopplane.fairness import (
    PlatformFairness,
    PlatformFairnessPolicy,
    PlatformFairnessRejected,
)

pytestmark = pytest.mark.anyio


async def _wait_for(predicate: object, timeout: float = 2.0) -> None:
    with anyio.fail_after(timeout):
        while not predicate():  # type: ignore[operator]
            await anyio.lowlevel.checkpoint()


@dataclass
class _HeldTurn:
    tenant_id: str
    release: anyio.Event


async def _hold_turn(
    fairness: PlatformFairness,
    tenant_id: str,
    release: anyio.Event,
    started: list[str],
) -> None:
    async with fairness.model_turn(tenant_id):
        started.append(tenant_id)
        await release.wait()


def _fairness(
    *,
    max_outstanding_per_tenant: int = 4,
    max_active_model_calls: int = 1,
    max_consecutive_starts: int = 1,
) -> PlatformFairness:
    return PlatformFairness(
        PlatformFairnessPolicy(
            max_outstanding_per_tenant=max_outstanding_per_tenant,
            max_active_model_calls=max_active_model_calls,
            max_consecutive_starts=max_consecutive_starts,
        )
    )


async def test_round_robin_progresses_waiting_tenant_before_same_tenant_burst() -> None:
    fairness = _fairness(max_active_model_calls=1, max_consecutive_starts=1)
    started: list[str] = []
    releases = [_HeldTurn("alice", anyio.Event()), _HeldTurn("alice", anyio.Event())]
    bob = _HeldTurn("bob", anyio.Event())

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(
            _hold_turn, fairness, releases[0].tenant_id, releases[0].release, started
        )
        await _wait_for(lambda: started == ["alice"])

        task_group.start_soon(
            _hold_turn, fairness, releases[1].tenant_id, releases[1].release, started
        )
        task_group.start_soon(_hold_turn, fairness, bob.tenant_id, bob.release, started)
        await anyio.lowlevel.checkpoint()

        releases[0].release.set()
        await _wait_for(lambda: len(started) >= 2)
        assert started[1] == "bob"

        bob.release.set()
        await _wait_for(lambda: len(started) == 3)
        assert started == ["alice", "bob", "alice"]

        releases[1].release.set()


async def test_single_tenant_starts_without_artificial_delay() -> None:
    fairness = _fairness(max_active_model_calls=1, max_consecutive_starts=1)

    with anyio.fail_after(1):
        async with fairness.model_turn("alice"):
            pass


async def test_quota_rejects_excess_and_release_allows_later_work() -> None:
    fairness = _fairness(max_outstanding_per_tenant=1)

    async with fairness.admit("alice"):
        with pytest.raises(PlatformFairnessRejected, match="capacity exceeded"):
            async with fairness.admit("alice"):
                pass

    async with fairness.admit("alice"):
        pass


async def test_quota_is_isolated_by_tenant() -> None:
    fairness = _fairness(max_outstanding_per_tenant=1)

    async with fairness.admit("alice"):
        async with fairness.admit("bob"):
            pass
        with pytest.raises(PlatformFairnessRejected):
            async with fairness.admit("alice"):
                pass


async def test_queued_waiter_cancellation_does_not_block_later_tenants() -> None:
    fairness = _fairness(max_active_model_calls=1, max_consecutive_starts=1)
    active_release = anyio.Event()
    queued_scope: anyio.CancelScope | None = None
    started: list[str] = []

    async def active() -> None:
        async with fairness.model_turn("alice"):
            started.append("alice")
            await active_release.wait()

    async def queued_then_cancelled() -> None:
        nonlocal queued_scope
        with anyio.CancelScope() as scope:
            queued_scope = scope
            async with fairness.model_turn("bob"):
                started.append("bob")

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(active)
        await _wait_for(lambda: started == ["alice"])

        task_group.start_soon(queued_then_cancelled)
        await _wait_for(lambda: queued_scope is not None)
        assert queued_scope is not None
        queued_scope.cancel()
        await anyio.lowlevel.checkpoint()

        active_release.set()
        with anyio.fail_after(1):
            async with fairness.model_turn("carol"):
                started.append("carol")
        assert started == ["alice", "carol"]


async def test_released_admission_context_is_idempotent() -> None:
    fairness = _fairness(max_outstanding_per_tenant=1)
    reservation = fairness.admit("alice")

    await reservation.__aenter__()
    await reservation.__aexit__(None, None, None)
    await reservation.__aexit__(None, None, None)

    async with fairness.admit("alice"):
        pass
