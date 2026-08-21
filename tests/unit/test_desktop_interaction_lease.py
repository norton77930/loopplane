"""Inner Interaction Lease race / owner correlation (078 T048/T052)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from profile import ProfileBusyError, ProfileOwnershipLock  # noqa: E402

from interaction import InteractionBusy, InteractionLease  # noqa: E402
from methods.interaction import InteractionMethods  # noqa: E402
from protocol import RpcError  # noqa: E402

pytestmark = pytest.mark.anyio

HOST_CALLS = {"n": 0}


def _host(tmp_path: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / f"store-{HOST_CALLS['n']}",
            ),
        ),
        working_scope=tmp_path,
    )


async def test_second_create_raises_busy_before_host_drive(tmp_path: Path) -> None:
    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    first = await methods.create_interactive({"mutation_id": "m1", "pane_id": "pane-a"})
    assert first["pane_id"] == "pane-a"
    with pytest.raises(RpcError) as exc:
        await methods.create_interactive({"mutation_id": "m2", "pane_id": "pane-b"})
    assert exc.value.category == "busy"
    # Safe correlation only — no secret host details
    data = exc.value.data or {}
    assert data.get("owner_pane_id") == "pane-a"
    assert "traceback" not in str(exc.value).lower()
    await lease.shutdown()


async def test_submit_requires_lease_owner_subscription(tmp_path: Path) -> None:
    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    created = await methods.create_interactive(
        {"mutation_id": "m1", "pane_id": "pane-a"}
    )
    sub = created["subscription_id"]
    with pytest.raises(RpcError) as exc:
        await methods.submit(
            {
                "mutation_id": "m2",
                "subscription_id": "not-the-owner",
                "prompt": "nope",
            }
        )
    assert exc.value.category in ("not_found", "invalid_state", "busy")
    # Owner can still submit
    result = await methods.submit(
        {"mutation_id": "m3", "subscription_id": sub, "prompt": "yes"}
    )
    assert result["accepted"] is True
    await lease.shutdown()


async def test_release_owner_then_other_pane_may_acquire(tmp_path: Path) -> None:
    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    a = await methods.create_interactive({"mutation_id": "m1", "pane_id": "a"})
    await methods.release_interactive(
        {"mutation_id": "m2", "subscription_id": a["subscription_id"]}
    )
    b = await methods.create_interactive({"mutation_id": "m3", "pane_id": "b"})
    assert b["pane_id"] == "b"
    await lease.shutdown()


async def test_release_retries_real_session_teardown_after_transient_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host(tmp_path)
    lease = InteractionLease()
    methods = InteractionMethods(host, lease, working_scope=tmp_path)
    created = await methods.create_interactive(
        {"mutation_id": "m1", "pane_id": "pane-1"}
    )
    subscription_id = created["subscription_id"]
    sub = lease.require_owner(subscription_id)
    attempts = 0
    original_cleanup = sub.session._cleanup
    assert original_cleanup is not None

    async def fail_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("teardown failed")
        result = original_cleanup()
        if result is not None:
            await result

    monkeypatch.setattr(sub.session, "_cleanup", fail_once)

    with pytest.raises(RuntimeError, match="teardown failed"):
        await lease.release(subscription_id)

    assert lease.active is sub
    assert lease.get(subscription_id) is sub

    assert await lease.release(subscription_id) is True
    assert attempts == 2
    assert lease.active is None
    assert lease.get(subscription_id) is None


async def test_session_aclose_is_idempotent_after_context_exit(tmp_path: Path) -> None:
    host = _host(tmp_path)

    async def sink(_event: object) -> None:
        return None

    async with host.session(sink) as session:
        await session.aclose()
        await session.aclose()

    await session.aclose()
    async with host.session(sink):
        pass


async def test_lease_busy_exception_zero_host_construction_on_contention(
    tmp_path: Path,
) -> None:
    """Direct lease: second acquire is busy without touching a second Host run."""

    host = _host(tmp_path)
    lease = InteractionLease()
    sub = await lease.create_interactive(host, pane_id="a", working_scope=tmp_path)
    with pytest.raises(InteractionBusy):
        await lease.create_interactive(host, pane_id="b", working_scope=tmp_path)
    assert lease.active is sub
    await lease.release(sub.subscription_id)


def test_outer_profile_lock_still_rejects_second_process(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    lock1 = ProfileOwnershipLock.for_root(root)
    lock1.acquire()
    try:
        lock2 = ProfileOwnershipLock.for_root(root)
        with pytest.raises(ProfileBusyError):
            lock2.acquire()
    finally:
        lock1.release()
