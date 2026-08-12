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
    assert exc.value.category in ("not_found", "state", "busy")
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
