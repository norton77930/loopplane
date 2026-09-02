"""Cross-process principal admission (085; ADR 0020).

A serving-layer lease in front of ``TenantHostPool`` / ``PlatformFairness``.
Grants are ephemeral and are not session, checkpoint, or event records.
Caps belong to the pool and fairness objects; this module only enforces them.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
    nullcontext,
    suppress,
)
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

import anyio

from loopplane.host import LoopPlaneHost
from loopplane.webapi.pool import TenantHostPool

_CONFLICT = "a run is already active"
_CAPACITY = "capacity exceeded"


class AdmissionRejected(Exception):
    """Public-safe admit failure. ``kind`` selects the existing HTTP phrase."""

    def __init__(self, kind: Literal["conflict", "capacity"]) -> None:
        self.kind = kind
        super().__init__(_CONFLICT if kind == "conflict" else _CAPACITY)


def admission_http(kind: str) -> tuple[int, str]:
    """Map a reject kind (or session-box marker) to the public HTTP pair."""

    if kind == "capacity":
        return 429, _CAPACITY
    return 409, _CONFLICT


def reject_if_over(
    *,
    in_flight: int,
    outstanding: int,
    in_flight_cap: int,
    outstanding_cap: int | None,
) -> None:
    if in_flight_cap < 1:
        raise ValueError("in_flight_cap must be >= 1")
    if outstanding_cap is not None and outstanding_cap < 1:
        raise ValueError("outstanding_cap must be >= 1")
    if in_flight + 1 > in_flight_cap:
        raise AdmissionRejected("conflict")
    if outstanding_cap is not None and outstanding + 1 > outstanding_cap:
        raise AdmissionRejected("capacity")


def outstanding_cap_for(host: LoopPlaneHost) -> int | None:
    """Cluster outstanding cap owned by the host's 072 fairness object, if any."""

    cap = getattr(host.platform_fairness, "max_outstanding_per_tenant", None)
    return cap if isinstance(cap, int) and cap >= 1 else None


@dataclass(frozen=True)
class AdmissionGrant:
    grant_id: str
    principal_id: str
    holder_id: str
    expires_at: datetime
    reserves_outstanding: bool


class AdmissionStore(Protocol):
    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        in_flight_cap: int,
        outstanding_cap: int | None,
        ttl: timedelta,
    ) -> AdmissionGrant: ...

    async def heartbeat(
        self, grant_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool: ...

    async def release(self, grant_id: str, holder_id: str) -> None: ...


class InMemoryAdmissionStore:
    """Process-lifetime grants. Single-process-honest; tests share one instance."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = anyio.Lock()
        self._grants: dict[str, AdmissionGrant] = {}

    def __repr__(self) -> str:
        return "InMemoryAdmissionStore()"

    def __str__(self) -> str:
        return "InMemoryAdmissionStore()"

    def _active(self, principal_id: str, now: datetime) -> list[AdmissionGrant]:
        live: list[AdmissionGrant] = []
        expired: list[str] = []
        for grant_id, grant in self._grants.items():
            if grant.principal_id != principal_id:
                continue
            if grant.expires_at <= now:
                expired.append(grant_id)
                continue
            live.append(grant)
        for grant_id in expired:
            self._grants.pop(grant_id, None)
        return live

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        in_flight_cap: int,
        outstanding_cap: int | None,
        ttl: timedelta,
    ) -> AdmissionGrant:
        async with self._lock:
            now = self._clock()
            live = self._active(principal_id, now)
            reject_if_over(
                in_flight=len(live),
                outstanding=sum(1 for grant in live if grant.reserves_outstanding),
                in_flight_cap=in_flight_cap,
                outstanding_cap=outstanding_cap,
            )
            grant = AdmissionGrant(
                grant_id=uuid.uuid4().hex,
                principal_id=principal_id,
                holder_id=holder_id,
                expires_at=now + ttl,
                reserves_outstanding=outstanding_cap is not None,
            )
            self._grants[grant.grant_id] = grant
            return grant

    async def heartbeat(self, grant_id: str, holder_id: str, *, ttl: timedelta) -> bool:
        async with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None or grant.holder_id != holder_id:
                return False
            now = self._clock()
            if grant.expires_at <= now:
                self._grants.pop(grant_id, None)
                return False
            self._grants[grant_id] = replace(grant, expires_at=now + ttl)
            return True

    async def release(self, grant_id: str, holder_id: str) -> None:
        async with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None or grant.holder_id != holder_id:
                return
            self._grants.pop(grant_id, None)


class AdmissionCoordinator:
    """Worker-side wrapper: take, heartbeat, release. Caps are passed to ``hold``."""

    def __init__(
        self,
        store: AdmissionStore,
        *,
        holder_id: str | None = None,
        ttl_seconds: float = 60.0,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._store = store
        self.holder_id = holder_id or uuid.uuid4().hex
        self._ttl = timedelta(seconds=ttl_seconds)

    def __repr__(self) -> str:
        return "AdmissionCoordinator()"

    def __str__(self) -> str:
        return "AdmissionCoordinator()"

    @asynccontextmanager
    async def hold(
        self,
        principal_id: str,
        *,
        in_flight_cap: int = 1,
        outstanding_cap: int | None = None,
    ) -> AsyncIterator[AdmissionGrant]:
        grant = await self._safe_take(
            principal_id,
            in_flight_cap=in_flight_cap,
            outstanding_cap=outstanding_cap,
        )
        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._heartbeat_loop, grant)
                try:
                    yield grant
                finally:
                    tg.cancel_scope.cancel()
        finally:
            with suppress(Exception):
                await self._store.release(grant.grant_id, self.holder_id)

    async def _safe_take(
        self,
        principal_id: str,
        *,
        in_flight_cap: int,
        outstanding_cap: int | None,
    ) -> AdmissionGrant:
        try:
            return await self._store.take(
                principal_id,
                self.holder_id,
                in_flight_cap=in_flight_cap,
                outstanding_cap=outstanding_cap,
                ttl=self._ttl,
            )
        except AdmissionRejected:
            raise
        except Exception as exc:
            raise AdmissionRejected("conflict") from exc

    async def _heartbeat_loop(self, grant: AdmissionGrant) -> None:
        interval = max(self._ttl / 3, timedelta(milliseconds=20))
        while True:
            await anyio.sleep(interval.total_seconds())
            try:
                alive = await self._store.heartbeat(
                    grant.grant_id, self.holder_id, ttl=self._ttl
                )
            except Exception:
                return
            if not alive:
                return


@asynccontextmanager
async def bound_run(
    *,
    admission: AdmissionCoordinator | None,
    pool: TenantHostPool | None,
    principal_id: str,
    outstanding_cap: int | None = None,
    hold_local: bool = True,
) -> AsyncIterator[None]:
    """Cluster grant (if configured) then, when this path did in 061, local in-flight.

    ``hold_local`` is the 061 path flag: ``POST /runs`` holds the pool semaphore;
    streaming and session did not. Cluster admission (ADR 0020 D8) still takes
    local in-flight on every path as defense in depth. ``admission=None`` must
    not expand 061 local in-flight onto those extra paths (G5 / D3).
    """

    in_flight_cap = pool.per_principal_in_flight if pool is not None else 1
    cluster: AbstractAsyncContextManager[object]
    if admission is None:
        cluster = nullcontext()
        take_local = hold_local and pool is not None
    else:
        cluster = admission.hold(
            principal_id,
            in_flight_cap=in_flight_cap,
            outstanding_cap=outstanding_cap,
        )
        take_local = pool is not None
    local: AbstractAsyncContextManager[object]
    local = (
        pool.in_flight(principal_id)
        if take_local and pool is not None
        else nullcontext()
    )
    async with cluster:
        async with local:
            yield
