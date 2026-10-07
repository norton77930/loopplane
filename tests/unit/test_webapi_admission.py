"""Unit 085: cross-process principal admission (ADR 0020)."""

from __future__ import annotations

import builtins
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import pytest

from loopplane.fairness import (
    InMemoryTurnPermitStore,
    PlatformFairness,
    PlatformFairnessPolicy,
)
from loopplane.model import ModelRequest, TextIncrement, TokenUsage, TurnEnd
from loopplane.webapi.admission import (
    AdmissionCoordinator,
    AdmissionRejected,
    InMemoryAdmissionStore,
    admission_http,
    outstanding_cap_for,
)

pytest.importorskip("fastapi")

from loopplane.webapi import (  # noqa: E402
    AdmissionCoordinator as ExportedCoordinator,
)
from loopplane.webapi import (
    InMemoryAdmissionStore as ExportedStore,
)
from loopplane.webapi import (
    PostgresAdmissionStore,
    TenantHostPool,
    create_app,
)
from loopplane.webapi.app import ModelHost  # noqa: E402
from tests.webapi_helpers import allow_all, build_test_host, make_client  # noqa: E402


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 2, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class _GateModel:
    def __init__(self, started: threading.Event, gate: threading.Event) -> None:
        self._started = started
        self._gate = gate

    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[object]:
        self._started.set()
        while not self._gate.is_set():
            await anyio.sleep(0.01)
        yield TextIncrement(text="ok")
        yield TurnEnd(stop_reason="end", usage=TokenUsage())


def test_admission_http_maps_kind() -> None:
    assert admission_http("conflict") == (409, "a run is already active")
    assert admission_http("capacity") == (429, "capacity exceeded")


def test_admission_rejected_phrases() -> None:
    conflict = AdmissionRejected("conflict")
    capacity = AdmissionRejected("capacity")
    assert str(conflict) == "a run is already active"
    assert conflict.kind == "conflict"
    assert str(capacity) == "capacity exceeded"
    assert capacity.kind == "capacity"


def test_store_and_coordinator_repr_are_public_safe() -> None:
    store = InMemoryAdmissionStore()
    coord = AdmissionCoordinator(store, holder_id="secret-holder")
    assert "secret-holder" not in repr(coord)
    assert "secret-holder" not in str(coord)
    assert (
        "grant" not in repr(store).lower() or repr(store) == "InMemoryAdmissionStore()"
    )


@pytest.mark.anyio
async def test_two_workers_same_principal_are_sequential() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice"):
        with pytest.raises(AdmissionRejected) as caught:
            async with right.hold("alice"):
                pass
        assert caught.value.kind == "conflict"
    async with right.hold("alice"):
        pass


@pytest.mark.anyio
async def test_two_principals_are_concurrent() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice"):
        async with right.hold("bob"):
            pass


@pytest.mark.anyio
async def test_in_flight_cap_is_cluster_scoped() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice", in_flight_cap=1):
        with pytest.raises(AdmissionRejected, match="already active"):
            async with right.hold("alice", in_flight_cap=1):
                pass
    async with right.hold("alice", in_flight_cap=1):
        pass


@pytest.mark.anyio
async def test_outstanding_cap_rejects_as_capacity() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice", in_flight_cap=2, outstanding_cap=1):
        with pytest.raises(AdmissionRejected) as caught:
            async with right.hold("alice", in_flight_cap=2, outstanding_cap=1):
                pass
        assert caught.value.kind == "capacity"


@pytest.mark.anyio
async def test_outstanding_cap_none_skips_that_check() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice", in_flight_cap=2):
        async with right.hold("alice", in_flight_cap=2):
            pass


@pytest.mark.anyio
async def test_expired_grant_allows_a_later_take() -> None:
    clock = _Clock()
    store = InMemoryAdmissionStore(clock=clock)
    first = await store.take(
        "alice",
        "w1",
        in_flight_cap=1,
        outstanding_cap=None,
        ttl=timedelta(seconds=1),
    )
    clock.now = clock.now + timedelta(seconds=2)
    second = await store.take(
        "alice",
        "w2",
        in_flight_cap=1,
        outstanding_cap=None,
        ttl=timedelta(seconds=1),
    )
    assert second.grant_id != first.grant_id
    assert second.holder_id == "w2"


@pytest.mark.anyio
async def test_live_hold_is_not_overwritten() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1", ttl_seconds=0.3)
    right = AdmissionCoordinator(store, holder_id="w2", ttl_seconds=0.3)
    async with left.hold("alice"):
        await anyio.sleep(0.15)
        with pytest.raises(AdmissionRejected):
            async with right.hold("alice"):
                pass


@pytest.mark.anyio
async def test_failed_renewal_ends_body_before_second_enters() -> None:
    """A liveness blip must end the in-flight body before another take."""

    body_inside = anyio.Event()

    class _BlipOnce(InMemoryAdmissionStore):
        def __init__(self) -> None:
            super().__init__()
            self.blips = 0

        async def heartbeat(
            self, grant_id: str, holder_id: str, *, ttl: timedelta
        ) -> bool:
            if body_inside.is_set() and self.blips == 0:
                self.blips += 1
                raise RuntimeError("blip")
            return await super().heartbeat(grant_id, holder_id, ttl=ttl)

    store = _BlipOnce()
    ttl = 0.06
    left = AdmissionCoordinator(store, holder_id="w1", ttl_seconds=ttl)
    right = AdmissionCoordinator(store, holder_id="w2", ttl_seconds=ttl)
    inside = 0
    peak = 0
    order: list[str] = []

    async def occupy() -> None:
        nonlocal inside, peak
        try:
            async with left.hold("alice", in_flight_cap=1):
                inside += 1
                peak = max(peak, inside)
                order.append("enter-1")
                body_inside.set()
                try:
                    await anyio.sleep(0.4)
                finally:
                    inside -= 1
                    order.append("leave-1")
        except BaseExceptionGroup:
            return

    async def challenger() -> None:
        nonlocal inside, peak
        await body_inside.wait()
        deadline = anyio.current_time() + 0.8
        while True:
            try:
                async with right.hold("alice", in_flight_cap=1):
                    inside += 1
                    peak = max(peak, inside)
                    order.append("enter-2")
                    inside -= 1
                    order.append("leave-2")
                    return
            except AdmissionRejected:
                if anyio.current_time() >= deadline:
                    raise
                await anyio.sleep(0.01)

    async with anyio.create_task_group() as tg:
        tg.start_soon(occupy)
        tg.start_soon(challenger)

    assert store.blips == 1
    assert peak == 1
    assert order.index("leave-1") < order.index("enter-2")
    later = await store.take(
        "alice",
        "w3",
        in_flight_cap=1,
        outstanding_cap=None,
        ttl=timedelta(seconds=30),
    )
    assert later.holder_id == "w3"


@pytest.mark.anyio
async def test_heartbeat_after_release_does_not_resurrect() -> None:
    store = InMemoryAdmissionStore()
    grant = await store.take(
        "alice",
        "w1",
        in_flight_cap=1,
        outstanding_cap=None,
        ttl=timedelta(seconds=30),
    )
    await store.release(grant.grant_id, "w1")
    assert (
        await store.heartbeat(grant.grant_id, "w1", ttl=timedelta(seconds=30)) is False
    )
    second = await store.take(
        "alice",
        "w2",
        in_flight_cap=1,
        outstanding_cap=None,
        ttl=timedelta(seconds=30),
    )
    assert second.holder_id == "w2"


@pytest.mark.anyio
async def test_concurrent_takes_have_exactly_one_winner() -> None:
    store = InMemoryAdmissionStore()
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    outcomes: list[str] = []

    async def attempt(coord: AdmissionCoordinator) -> None:
        try:
            async with coord.hold("alice"):
                outcomes.append("won")
                await anyio.sleep(0.05)
        except AdmissionRejected:
            outcomes.append("lost")

    async with anyio.create_task_group() as tg:
        tg.start_soon(attempt, left)
        tg.start_soon(attempt, right)
    assert outcomes.count("won") == 1
    assert outcomes.count("lost") == 1


@pytest.mark.anyio
async def test_store_error_fails_closed() -> None:
    class _Boom:
        async def take(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("store unavailable")

        async def heartbeat(self, *args: object, **kwargs: object) -> bool:
            return False

        async def release(self, *args: object, **kwargs: object) -> None:
            return None

    coord = AdmissionCoordinator(_Boom())  # type: ignore[arg-type]
    with pytest.raises(AdmissionRejected) as caught:
        async with coord.hold("alice"):
            pass
    assert caught.value.kind == "conflict"
    assert "store unavailable" not in str(caught.value)


def test_outstanding_cap_for_reads_public_host_fairness(tmp_path: Path) -> None:
    fairness = PlatformFairness(PlatformFairnessPolicy(max_outstanding_per_tenant=3))
    host = build_test_host(tmp_path, platform_fairness=fairness)
    assert host.platform_fairness is fairness
    assert outstanding_cap_for(host) == 3
    assert outstanding_cap_for(build_test_host(tmp_path / "bare")) is None


def test_create_app_without_admission_still_runs(tmp_path: Path) -> None:
    host = build_test_host(tmp_path)
    client = make_client(create_app(host, authenticator=allow_all))
    response = client.post("/v1/runs", json={"prompt": "hi"})
    assert response.status_code == 200


def _pooled_two_model_app(
    tmp_path: Path, *, admission: AdmissionCoordinator | None = None
):
    def factory(model: str | None = None):
        return build_test_host(tmp_path / (model or "default"))

    pool = TenantHostPool(factory, per_principal_in_flight=1)
    default = factory()
    beta = factory("beta")
    return create_app(
        default,
        authenticator=allow_all,
        host_pool=pool,
        models={"beta": ModelHost(label="beta", host=beta)},
        admission=admission,
    )


def test_pooled_idle_session_does_not_block_runs_without_admission(
    tmp_path: Path,
) -> None:
    """G5 / ADR 0020 D3: admission off must not expand 061 in_flight onto sessions."""

    with make_client(_pooled_two_model_app(tmp_path)) as client:
        opened = client.post("/v1/sessions")
        assert opened.status_code == 200
        run = client.post("/v1/runs", json={"prompt": "hi", "model": "beta"})
        assert run.status_code == 200


def test_pooled_idle_session_blocks_runs_when_admission_is_on(tmp_path: Path) -> None:
    """ADR 0020 D8: admission on wraps session; same principal's other host is 409."""

    coord = ExportedCoordinator(ExportedStore(), holder_id="w1")
    with make_client(_pooled_two_model_app(tmp_path, admission=coord)) as client:
        opened = client.post("/v1/sessions")
        assert opened.status_code == 200
        run = client.post("/v1/runs", json={"prompt": "hi", "model": "beta"})
        assert run.status_code == 409
        assert run.json() == {"detail": "a run is already active"}


def test_admission_conflict_holds_when_turn_permits_are_configured(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    gate = threading.Event()
    store = ExportedStore()
    left = ExportedCoordinator(store, holder_id="w1")
    right = ExportedCoordinator(store, holder_id="w2")
    turns = InMemoryTurnPermitStore()
    fairness_a = PlatformFairness(
        PlatformFairnessPolicy(max_outstanding_per_tenant=4), turn_permits=turns
    )
    fairness_b = PlatformFairness(
        PlatformFairnessPolicy(max_outstanding_per_tenant=4), turn_permits=turns
    )
    host_a = build_test_host(
        tmp_path / "a", model=_GateModel(started, gate), platform_fairness=fairness_a
    )
    host_b = build_test_host(tmp_path / "b", platform_fairness=fairness_b)
    client_a = make_client(create_app(host_a, authenticator=allow_all, admission=left))
    client_b = make_client(create_app(host_b, authenticator=allow_all, admission=right))
    first: list[int] = []

    def _run_first() -> None:
        first.append(client_a.post("/v1/runs", json={"prompt": "one"}).status_code)

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert started.wait(timeout=5)
    second = client_b.post("/v1/runs", json={"prompt": "two"})
    assert second.status_code == 409
    assert second.json() == {"detail": "a run is already active"}
    gate.set()
    thread.join(timeout=5)
    assert first == [200]


def test_overlapping_http_runs_conflict_across_workers(tmp_path: Path) -> None:
    started = threading.Event()
    gate = threading.Event()
    store = ExportedStore()
    left = ExportedCoordinator(store, holder_id="w1")
    right = ExportedCoordinator(store, holder_id="w2")
    host_a = build_test_host(tmp_path / "a", model=_GateModel(started, gate))
    host_b = build_test_host(tmp_path / "b")
    client_a = make_client(create_app(host_a, authenticator=allow_all, admission=left))
    client_b = make_client(create_app(host_b, authenticator=allow_all, admission=right))
    first: list[int] = []

    def _run_first() -> None:
        first.append(client_a.post("/v1/runs", json={"prompt": "one"}).status_code)

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert started.wait(timeout=5)
    second = client_b.post("/v1/runs", json={"prompt": "two"})
    assert second.status_code == 409
    assert second.json() == {"detail": "a run is already active"}
    gate.set()
    thread.join(timeout=5)
    assert first == [200]


def test_http_outstanding_follows_host_fairness(tmp_path: Path) -> None:
    started = threading.Event()
    gate = threading.Event()
    store = ExportedStore()
    left = ExportedCoordinator(store, holder_id="w1")
    right = ExportedCoordinator(store, holder_id="w2")
    fairness_a = PlatformFairness(PlatformFairnessPolicy(max_outstanding_per_tenant=1))
    fairness_b = PlatformFairness(PlatformFairnessPolicy(max_outstanding_per_tenant=1))

    def factory_a(model: str | None = None):
        return build_test_host(
            tmp_path / "a",
            model=_GateModel(started, gate),
            platform_fairness=fairness_a,
        )

    def factory_b(model: str | None = None):
        return build_test_host(tmp_path / "b", platform_fairness=fairness_b)

    client_a = make_client(
        create_app(
            factory_a(),
            authenticator=allow_all,
            host_pool=TenantHostPool(factory_a, per_principal_in_flight=2),
            admission=left,
        )
    )
    client_b = make_client(
        create_app(
            factory_b(),
            authenticator=allow_all,
            host_pool=TenantHostPool(factory_b, per_principal_in_flight=2),
            admission=right,
        )
    )

    def _run_first() -> None:
        client_a.post("/v1/runs", json={"prompt": "one"})

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert started.wait(timeout=5)
    second = client_b.post("/v1/runs", json={"prompt": "two"})
    assert second.status_code == 429
    assert second.json() == {"detail": "capacity exceeded"}
    gate.set()
    thread.join(timeout=5)


def test_overlapping_event_stream_uses_public_safe_error(tmp_path: Path) -> None:
    started = threading.Event()
    gate = threading.Event()
    store = ExportedStore()
    left = ExportedCoordinator(store, holder_id="w1")
    right = ExportedCoordinator(store, holder_id="w2")
    host_a = build_test_host(tmp_path / "a", model=_GateModel(started, gate))
    host_b = build_test_host(tmp_path / "b")
    client_a = make_client(create_app(host_a, authenticator=allow_all, admission=left))
    client_b = make_client(create_app(host_b, authenticator=allow_all, admission=right))

    def _run_first() -> None:
        client_a.post("/v1/runs", json={"prompt": "one"})

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert started.wait(timeout=5)
    streamed = client_b.post("/v1/runs/events", json={"prompt": "two"})
    assert streamed.status_code == 200
    body = streamed.text
    assert "a run is already active" in body
    assert "event: error" in body
    gate.set()
    thread.join(timeout=5)


@pytest.mark.anyio
async def test_postgres_store_take_release_and_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("psycopg")
    from tests import admission_pg_stub

    admission_pg_stub.patch_psycopg(monkeypatch)
    store = PostgresAdmissionStore(f"postgresql://stub/{tmp_path.name}")
    left = AdmissionCoordinator(store, holder_id="w1")
    right = AdmissionCoordinator(store, holder_id="w2")
    async with left.hold("alice"):
        with pytest.raises(AdmissionRejected) as caught:
            async with right.hold("alice"):
                pass
        assert caught.value.kind == "conflict"
    async with right.hold("alice"):
        pass


def test_postgres_dsn_is_never_echoed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("psycopg")
    from tests import admission_pg_stub

    admission_pg_stub.patch_psycopg(monkeypatch)
    dsn = "postgresql://user:do-not-echo-pw@host/db"
    store = PostgresAdmissionStore(dsn)
    assert "do-not-echo-pw" not in repr(store)
    assert "do-not-echo-pw" not in str(store)


def test_postgres_requires_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "psycopg":
            raise ImportError("simulated: psycopg not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        PostgresAdmissionStore("postgresql://x/db")
