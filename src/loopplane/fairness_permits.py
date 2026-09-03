"""Cluster turn-permit stores (086; ADR 0021). Injected into PlatformFairness."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

import anyio


class TurnPermitUnavailable(Exception):
    """Cluster turn store could not confirm a permit. Callers may degrade."""


@dataclass(frozen=True)
class TurnPermit:
    permit_id: str
    principal_id: str
    holder_id: str
    expires_at: datetime


class TurnPermitStore(Protocol):
    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ) -> TurnPermit: ...

    async def heartbeat(
        self, permit_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool: ...

    async def release(self, permit_id: str, holder_id: str) -> None: ...


@dataclass
class PermitWaiter:
    waiter_id: str
    principal_id: str
    holder_id: str
    active_cap: int
    consecutive_cap: int
    ttl: timedelta
    event: anyio.Event | None = None
    permit: TurnPermit | None = None
    enqueued_at: datetime | None = None


@dataclass
class PermitBook:
    permits: dict[str, TurnPermit] = field(default_factory=dict)
    waiters: list[PermitWaiter] = field(default_factory=list)
    last_started: str | None = None
    consecutive: int = 0


def schedule(book: PermitBook, now: datetime) -> None:
    """Grant fair-next waiters into permits. Shared by in-memory and Postgres."""

    expired = [
        permit_id
        for permit_id, permit in book.permits.items()
        if permit.expires_at <= now
    ]
    for permit_id in expired:
        book.permits.pop(permit_id, None)
    while book.waiters:
        index = _next_index(book)
        waiter = book.waiters[index]
        if len(book.permits) >= waiter.active_cap:
            return
        book.waiters.pop(index)
        permit = TurnPermit(
            permit_id=uuid.uuid4().hex,
            principal_id=waiter.principal_id,
            holder_id=waiter.holder_id,
            expires_at=now + waiter.ttl,
        )
        book.permits[permit.permit_id] = permit
        if waiter.principal_id == book.last_started:
            book.consecutive += 1
        else:
            book.last_started = waiter.principal_id
            book.consecutive = 1
        waiter.permit = permit
        if waiter.event is not None:
            waiter.event.set()


def _next_index(book: PermitBook) -> int:
    if (
        book.last_started is not None
        and book.waiters
        and book.consecutive >= book.waiters[0].consecutive_cap
    ):
        for index, waiter in enumerate(book.waiters):
            if waiter.principal_id != book.last_started:
                return index
    return 0


async def _heartbeat_loop(
    store: TurnPermitStore,
    permit: TurnPermit,
    holder_id: str,
    ttl: timedelta,
) -> None:
    interval = max(ttl / 3, timedelta(milliseconds=20))
    while True:
        await anyio.sleep(interval.total_seconds())
        try:
            alive = await store.heartbeat(permit.permit_id, holder_id, ttl=ttl)
        except TurnPermitUnavailable:
            return
        if not alive:
            return


@asynccontextmanager
async def hold_turn(
    store: TurnPermitStore,
    principal_id: str,
    holder_id: str,
    *,
    active_cap: int,
    consecutive_cap: int,
    ttl: timedelta,
) -> AsyncIterator[TurnPermit]:
    """Take, heartbeat, release. The 085 hold() shape for turn permits."""

    permit = await store.take(
        principal_id,
        holder_id,
        active_cap=active_cap,
        consecutive_cap=consecutive_cap,
        ttl=ttl,
    )
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_heartbeat_loop, store, permit, holder_id, ttl)
            try:
                yield permit
            finally:
                tg.cancel_scope.cancel()
    finally:
        with suppress(Exception):
            await store.release(permit.permit_id, holder_id)


class InMemoryTurnPermitStore:
    """Process-lifetime turn permits. Tests share one instance across workers."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = anyio.Lock()
        self._book = PermitBook()

    def __repr__(self) -> str:
        return "InMemoryTurnPermitStore()"

    def __str__(self) -> str:
        return "InMemoryTurnPermitStore()"

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ) -> TurnPermit:
        if active_cap < 1 or consecutive_cap < 1:
            raise ValueError("caps must be >= 1")
        waiter = PermitWaiter(
            waiter_id=uuid.uuid4().hex,
            principal_id=principal_id,
            holder_id=holder_id,
            active_cap=active_cap,
            consecutive_cap=consecutive_cap,
            ttl=ttl,
            event=anyio.Event(),
        )
        async with self._lock:
            self._book.waiters.append(waiter)
            schedule(self._book, self._clock())
        try:
            while waiter.permit is None:
                await waiter.event.wait()  # type: ignore[union-attr]
            return waiter.permit
        except BaseException:
            async with self._lock:
                if waiter.permit is not None:
                    self._book.permits.pop(waiter.permit.permit_id, None)
                else:
                    with suppress(ValueError):
                        self._book.waiters.remove(waiter)
                schedule(self._book, self._clock())
            raise

    async def heartbeat(
        self, permit_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool:
        async with self._lock:
            permit = self._book.permits.get(permit_id)
            if permit is None or permit.holder_id != holder_id:
                return False
            now = self._clock()
            if permit.expires_at <= now:
                self._book.permits.pop(permit_id, None)
                schedule(self._book, now)
                return False
            self._book.permits[permit_id] = replace(permit, expires_at=now + ttl)
            return True

    async def release(self, permit_id: str, holder_id: str) -> None:
        async with self._lock:
            permit = self._book.permits.get(permit_id)
            if permit is None or permit.holder_id != holder_id:
                return
            self._book.permits.pop(permit_id, None)
            schedule(self._book, self._clock())
