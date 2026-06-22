"""Unit 061: per-principal host pool (TenantHostPool) + create_app wiring.

Offline / in-process. Tests the pool's load-bearing concurrency property at the unit
level (per-principal hosts → cross-principal concurrency; per-host reuse; bounds;
isolation; in-flight cap) plus that ``create_app`` routes per-principal when a pool is
given and is byte-identical (a single shared host) when it is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy  # noqa: E402
from loopplane.host import LoopPlaneHost  # noqa: E402
from loopplane.webapi import TenantHostPool, create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    make_client,
    multi_text_model,
)


def _factory(tmp_path: Path):
    def make(model: str | None = None) -> LoopPlaneHost:
        return build_test_host(tmp_path, model=multi_text_model("a", "b", "c"))

    return make


# --- pool unit: per-principal hosts -----------------------------------------


def test_host_for_reuses_per_principal_and_isolates_principals(tmp_path: Path) -> None:
    pool = TenantHostPool(_factory(tmp_path))
    a1 = pool.host_for("alice")
    a2 = pool.host_for("alice")
    b1 = pool.host_for("bob")
    assert a1 is a2  # reused per principal
    assert a1 is not b1  # a distinct host per principal -> cross-principal concurrency


def test_host_for_keys_by_model(tmp_path: Path) -> None:
    pool = TenantHostPool(_factory(tmp_path))
    assert pool.host_for("alice", "m1") is pool.host_for("alice", "m1")
    assert pool.host_for("alice", "m1") is not pool.host_for("alice", "m2")


def test_max_principals_bounds_new_principals(tmp_path: Path) -> None:
    pool = TenantHostPool(_factory(tmp_path), max_principals=1)
    pool.host_for("alice")  # 1st principal — OK
    pool.host_for("alice", "m2")  # same principal, new model — not a new principal
    with pytest.raises(RuntimeError, match="capacity"):
        pool.host_for("bob")  # a 2nd principal — rejected (bounded)


def test_build_failure_does_not_corrupt_other_principals(tmp_path: Path) -> None:
    def make(model: str | None = None) -> LoopPlaneHost:
        if model == "boom":
            raise ValueError("factory boom")
        return build_test_host(tmp_path, model=multi_text_model("a"))

    pool = TenantHostPool(make)
    with pytest.raises(ValueError, match="boom"):
        pool.host_for("alice", "boom")
    good = pool.host_for("bob")  # another principal still works
    assert isinstance(good, LoopPlaneHost)
    assert ("alice", "boom") not in pool._hosts  # noqa: SLF001 — no corrupt entry


def test_invalid_caps_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="per_principal_in_flight"):
        TenantHostPool(_factory(tmp_path), per_principal_in_flight=0)
    with pytest.raises(ValueError, match="max_principals"):
        TenantHostPool(_factory(tmp_path), max_principals=0)


@pytest.mark.anyio
async def test_in_flight_cap_rejects_a_second_concurrent_run(tmp_path: Path) -> None:
    pool = TenantHostPool(_factory(tmp_path), per_principal_in_flight=1)
    async with pool.in_flight("alice"):
        with pytest.raises(RuntimeError, match="in-flight"):
            async with pool.in_flight("alice"):
                pass
    # released on exit -> can acquire again
    async with pool.in_flight("alice"):
        pass


@pytest.mark.anyio
async def test_in_flight_is_per_principal(tmp_path: Path) -> None:
    pool = TenantHostPool(_factory(tmp_path), per_principal_in_flight=1)
    async with pool.in_flight("alice"):
        async with pool.in_flight("bob"):  # a different principal is unaffected
            pass


# --- create_app wiring: pool vs default (byte-identical) ----------------------


def test_create_app_with_pool_routes_to_a_per_principal_host(tmp_path: Path) -> None:
    built: list[LoopPlaneHost] = []

    def make(model: str | None = None) -> LoopPlaneHost:
        host = build_test_host(tmp_path, model=multi_text_model("x", "y"))
        built.append(host)
        return host

    pool = TenantHostPool(make)
    default = build_test_host(tmp_path, model=multi_text_model("z"))
    client = make_client(create_app(default, authenticator=allow_all, host_pool=pool))
    response = client.post("/v1/runs", json={"prompt": "hi"})
    assert response.status_code == 200
    assert len(built) == 1  # the pool built a per-principal host
    assert built[0] is not default  # the run did NOT use the shared default host


def test_create_app_default_uses_the_single_shared_host(tmp_path: Path) -> None:
    default = build_test_host(tmp_path, model=multi_text_model("a", "b"))
    client = make_client(create_app(default, authenticator=allow_all))  # no pool
    response = client.post("/v1/runs", json={"prompt": "hi"})
    assert (
        response.status_code == 200
    )  # default path runs on the shared host (unchanged)


def test_host_pool_default_path_does_not_require_platform_fairness(
    tmp_path: Path,
) -> None:
    pool = TenantHostPool(_factory(tmp_path))
    default = build_test_host(tmp_path, model=multi_text_model("z"))
    client = make_client(create_app(default, authenticator=allow_all, host_pool=pool))

    response = client.post("/v1/runs", json={"prompt": "hi"})

    assert response.status_code == 200


def test_host_pool_accepts_hosts_with_shared_platform_fairness(
    tmp_path: Path,
) -> None:
    fairness = PlatformFairness(
        PlatformFairnessPolicy(
            max_outstanding_per_tenant=2,
            max_active_model_calls=1,
            max_consecutive_starts=1,
        )
    )

    def make(model: str | None = None) -> LoopPlaneHost:
        return build_test_host(
            tmp_path,
            model=multi_text_model("x", "y"),
            platform_fairness=fairness,
        )

    pool = TenantHostPool(make)
    default = build_test_host(tmp_path, model=multi_text_model("z"))
    client = make_client(create_app(default, authenticator=allow_all, host_pool=pool))

    response = client.post("/v1/runs", json={"prompt": "hi"})

    assert response.status_code == 200
