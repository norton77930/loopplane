"""Explicit weighted model-start fairness (087); existing fairness stays unchanged."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Protocol, TypeVar

import anyio

from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy
from loopplane.fairness_permits import (
    TurnPermit,
    TurnPermitStore,
    TurnPermitUnavailable,
)

__all__ = [
    "WeightedTurnPolicy",
    "WeightedTurnPermitStore",
    "WeightedInMemoryTurnPermitStore",
    "WeightedPlatformFairness",
]

_T = TypeVar("_T")
_TTL = timedelta(seconds=60)


@dataclass(frozen=True, repr=False)
class WeightedTurnPolicy:
    weights: Mapping[str, int]
    active_cap: int = field(kw_only=True)
    consecutive_cap: int = field(kw_only=True)

    def __post_init__(self) -> None:
        copied = dict(self.weights)
        if any(not isinstance(key, str) or not key for key in copied):
            raise ValueError("weight tenant identifiers must be nonempty strings")
        if any(
            type(value) is not int or not 1 <= value <= 100 for value in copied.values()
        ):
            raise ValueError("weights must be integers from 1 through 100")
        if any(
            type(value) is not int or value < 1
            for value in (self.active_cap, self.consecutive_cap)
        ):
            raise ValueError("policy caps must be positive integers")
        object.__setattr__(self, "weights", MappingProxyType(copied))

    def __repr__(self) -> str:
        return "WeightedTurnPolicy(<redacted>)"


class WeightedTurnPermitStore(TurnPermitStore, Protocol):
    @property
    def policy(self) -> WeightedTurnPolicy: ...


@dataclass
class _Request:
    holder_id: str
    tenant: str
    expires_at: datetime
    ttl: timedelta


@dataclass
class _Book:
    waiters: list[_Request] = field(default_factory=list)
    permits: dict[str, TurnPermit] = field(default_factory=dict)
    scores: dict[str, int] = field(default_factory=dict)
    last: str | None = None
    consecutive: int = 0


def _prune(book: _Book, now: datetime) -> None:
    book.waiters = [waiter for waiter in book.waiters if waiter.expires_at > now]
    book.permits = {
        key: permit for key, permit in book.permits.items() if permit.expires_at > now
    }
    ready = {waiter.tenant for waiter in book.waiters}
    book.scores = {
        tenant: score for tenant, score in book.scores.items() if tenant in ready
    }


def _schedule(book: _Book, policy: WeightedTurnPolicy, now: datetime) -> None:
    _prune(book, now)
    while book.waiters and len(book.permits) < policy.active_cap:
        tenants = list(dict.fromkeys(waiter.tenant for waiter in book.waiters))
        eligible = tenants
        if book.consecutive >= policy.consecutive_cap and len(tenants) > 1:
            eligible = [tenant for tenant in tenants if tenant != book.last]
        total = sum(policy.weights.get(tenant, 1) for tenant in tenants)
        for tenant in tenants:
            book.scores[tenant] = book.scores.get(tenant, 0) + policy.weights.get(
                tenant, 1
            )
        # Tenant spelling does not affect shares; ties follow queue order.
        selected = max(eligible, key=lambda tenant: book.scores[tenant])
        book.scores[selected] -= total
        # A binding hard cap can make the requested ratio impossible. Do not bank
        # unlimited debt/credit while that protection is taking precedence.
        book.scores = {
            tenant: max(-total, min(total, book.scores[tenant])) for tenant in tenants
        }
        index = next(
            i for i, waiter in enumerate(book.waiters) if waiter.tenant == selected
        )
        waiter = book.waiters.pop(index)
        permit = TurnPermit(
            uuid.uuid4().hex, selected, waiter.holder_id, now + waiter.ttl
        )
        book.permits[permit.permit_id] = permit
        book.consecutive = book.consecutive + 1 if book.last == selected else 1
        book.last = selected
        if not any(pending.tenant == selected for pending in book.waiters):
            book.scores.pop(selected, None)


class _PollingStore:
    def __init__(self, policy: WeightedTurnPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> WeightedTurnPolicy:
        return self._policy

    async def _mutate(self, operation: Callable[[_Book, datetime], _T]) -> _T:
        raise NotImplementedError

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ) -> TurnPermit:
        if (active_cap, consecutive_cap) != (
            self.policy.active_cap,
            self.policy.consecutive_cap,
        ):
            raise ValueError("weighted turn policy mismatch")
        if ttl <= timedelta(0):
            raise ValueError("turn lease must be positive")

        def acquire(book: _Book, now: datetime) -> TurnPermit | None:
            _prune(book, now)
            for permit in book.permits.values():
                if permit.holder_id == holder_id:
                    if permit.principal_id != principal_id:
                        raise ValueError("turn acquisition identity conflict")
                    return permit
            mine = next(
                (waiter for waiter in book.waiters if waiter.holder_id == holder_id),
                None,
            )
            if mine is None:
                book.waiters.append(_Request(holder_id, principal_id, now + ttl, ttl))
            else:
                if mine.tenant != principal_id:
                    raise ValueError("turn acquisition identity conflict")
                mine.expires_at = now + ttl
            _schedule(book, self.policy, now)
            return next(
                (
                    permit
                    for permit in book.permits.values()
                    if permit.holder_id == holder_id
                ),
                None,
            )

        try:
            while True:
                permit = await self._mutate(acquire)
                if permit is not None:
                    return permit
                await anyio.sleep(min(0.02, ttl.total_seconds() / 3))
        except BaseException:
            with anyio.CancelScope(shield=True):
                with suppress(TurnPermitUnavailable):
                    await self._mutate(
                        lambda book, now: self._cancel(
                            book, now, holder_id, principal_id
                        )
                    )
            raise

    def _cancel(self, book: _Book, now: datetime, holder: str, principal: str) -> None:
        book.waiters = [
            waiter
            for waiter in book.waiters
            if (waiter.holder_id, waiter.tenant) != (holder, principal)
        ]
        book.permits = {
            key: permit
            for key, permit in book.permits.items()
            if (permit.holder_id, permit.principal_id) != (holder, principal)
        }
        _schedule(book, self.policy, now)

    async def heartbeat(
        self, permit_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool:
        if ttl <= timedelta(0):
            raise ValueError("turn lease must be positive")

        def renew(book: _Book, now: datetime) -> bool:
            _prune(book, now)
            permit = book.permits.get(permit_id)
            if permit is None or permit.holder_id != holder_id:
                _schedule(book, self.policy, now)
                return False
            book.permits[permit_id] = replace(permit, expires_at=now + ttl)
            return True

        return await self._mutate(renew)

    async def release(self, permit_id: str, holder_id: str) -> None:
        def release(book: _Book, now: datetime) -> None:
            permit = book.permits.get(permit_id)
            if permit is not None and permit.holder_id == holder_id:
                del book.permits[permit_id]
            _schedule(book, self.policy, now)

        await self._mutate(release)


class WeightedInMemoryTurnPermitStore(_PollingStore):
    """One process only; share one instance between simulated workers."""

    def __init__(
        self, policy: WeightedTurnPolicy, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        super().__init__(policy)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._book = _Book()
        self._lock = anyio.Lock()

    def __repr__(self) -> str:
        return "WeightedInMemoryTurnPermitStore()"

    async def _mutate(self, operation: Callable[[_Book, datetime], _T]) -> _T:
        async with self._lock:
            return operation(self._book, self._clock())


async def _renew(store: TurnPermitStore, permit: TurnPermit) -> None:
    while True:
        await anyio.sleep(_TTL.total_seconds() / 3)
        try:
            alive = await store.heartbeat(permit.permit_id, permit.holder_id, ttl=_TTL)
        except TurnPermitUnavailable as exc:
            raise RuntimeError("turn lease lost") from exc
        if not alive:
            raise RuntimeError("turn lease lost")


@asynccontextmanager
async def _held(store: TurnPermitStore, permit: TurnPermit) -> AsyncIterator[None]:
    body_error: BaseException | None = None
    try:
        async with anyio.create_task_group() as group:
            group.start_soon(_renew, store, permit)
            try:
                yield
            except BaseException as exc:
                body_error = exc
            finally:
                group.cancel_scope.cancel()
    finally:
        with anyio.CancelScope(shield=True):
            with suppress(TurnPermitUnavailable):
                await store.release(permit.permit_id, permit.holder_id)
    if body_error is not None:
        raise body_error


class WeightedPlatformFairness:
    """Opt-in cluster-first turns with unchanged admission and local hard caps."""

    def __init__(
        self, policy: PlatformFairnessPolicy, *, turn_permits: WeightedTurnPermitStore
    ) -> None:
        if (policy.max_active_model_calls, policy.max_consecutive_starts) != (
            turn_permits.policy.active_cap,
            turn_permits.policy.consecutive_cap,
        ):
            raise ValueError("weighted turn policy mismatch")
        self._admission = PlatformFairness(policy)
        self._store = turn_permits
        self._local_slots = anyio.CapacityLimiter(policy.max_active_model_calls)

    def __repr__(self) -> str:
        return "WeightedPlatformFairness()"

    @property
    def max_outstanding_per_tenant(self) -> int:
        return self._admission.max_outstanding_per_tenant

    @asynccontextmanager
    async def admit(self, tenant_id: str) -> AsyncIterator[None]:
        admission = self._admission.admit(tenant_id)
        await admission.__aenter__()
        try:
            yield
        finally:
            with anyio.CancelScope(shield=True):
                await admission.__aexit__(None, None, None)

    def model_turn(self, tenant_id: str) -> AbstractAsyncContextManager[object]:
        return self._turn(tenant_id)

    async def _take(self, store: WeightedTurnPermitStore, tenant: str) -> TurnPermit:
        return await store.take(
            tenant,
            uuid.uuid4().hex,
            active_cap=store.policy.active_cap,
            consecutive_cap=store.policy.consecutive_cap,
            ttl=_TTL,
        )

    def _claim_local(self) -> bool:
        try:
            self._local_slots.acquire_nowait()
        except anyio.WouldBlock:
            return False
        return True

    @asynccontextmanager
    async def _turn(self, tenant_id: str) -> AsyncIterator[None]:
        while True:
            try:
                permit = await self._take(self._store, tenant_id)
            except TurnPermitUnavailable:
                async with self._local_slots:
                    async with self._admission.model_turn(tenant_id):
                        yield
                return
            if not self._claim_local():
                await self._store.release(permit.permit_id, permit.holder_id)
                await self._local_slots.acquire()
                self._local_slots.release()
                continue
            try:
                async with _held(self._store, permit):
                    yield
            finally:
                self._local_slots.release()
            return
