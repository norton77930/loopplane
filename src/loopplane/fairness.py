"""In-process platform fairness for tenant-scoped model-call work (072)."""

from __future__ import annotations

from collections import defaultdict
from contextlib import AbstractAsyncContextManager, suppress
from dataclasses import dataclass
from typing import Protocol

import anyio


class PlatformFairnessRejected(RuntimeError):
    """Raised when local tenant quota rejects work before admission."""


class PlatformFairnessGate(Protocol):
    def admit(self, tenant_id: str) -> AbstractAsyncContextManager[object]: ...

    def model_turn(self, tenant_id: str) -> AbstractAsyncContextManager[object]: ...


@dataclass(frozen=True)
class PlatformFairnessPolicy:
    max_outstanding_per_tenant: int
    max_active_model_calls: int = 1
    max_consecutive_starts: int = 1

    def __post_init__(self) -> None:
        for field in (
            "max_outstanding_per_tenant",
            "max_active_model_calls",
            "max_consecutive_starts",
        ):
            if getattr(self, field) < 1:
                raise ValueError(f"{field} must be >= 1")


@dataclass
class _Waiter:
    tenant_id: str
    event: anyio.Event
    granted: bool = False


class PlatformFairness:
    """A process-local tenant quota and fair model-turn gate."""

    def __init__(self, policy: PlatformFairnessPolicy) -> None:
        self._policy = policy
        self._lock = anyio.Lock()
        self._outstanding: defaultdict[str, int] = defaultdict(int)
        self._waiters: list[_Waiter] = []
        self._active_model_calls = 0
        self._last_started_tenant: str | None = None
        self._consecutive_starts = 0

    @property
    def max_outstanding_per_tenant(self) -> int:
        return self._policy.max_outstanding_per_tenant

    def admit(self, tenant_id: str) -> _Admission:
        return _Admission(self, tenant_id)

    def model_turn(self, tenant_id: str) -> _ModelTurn:
        return _ModelTurn(self, tenant_id)

    async def _enter_admission(self, tenant_id: str) -> None:
        async with self._lock:
            if self._outstanding[tenant_id] >= self._policy.max_outstanding_per_tenant:
                raise PlatformFairnessRejected("capacity exceeded")
            self._outstanding[tenant_id] += 1

    async def _exit_admission(self, tenant_id: str) -> None:
        async with self._lock:
            if self._outstanding[tenant_id] <= 1:
                self._outstanding.pop(tenant_id, None)
            else:
                self._outstanding[tenant_id] -= 1

    async def _enter_model_turn(self, tenant_id: str) -> _Waiter:
        waiter = _Waiter(tenant_id=tenant_id, event=anyio.Event())
        async with self._lock:
            self._waiters.append(waiter)
            self._wake_waiters_locked()
        try:
            while True:
                async with self._lock:
                    if waiter.granted:
                        return waiter
                await waiter.event.wait()
        except BaseException:
            async with self._lock:
                if waiter.granted:
                    self._release_model_turn_locked()
                else:
                    with suppress(ValueError):
                        self._waiters.remove(waiter)
                    self._wake_waiters_locked()
            raise

    async def _exit_model_turn(self, waiter: _Waiter) -> None:
        async with self._lock:
            if waiter.granted:
                waiter.granted = False
                self._release_model_turn_locked()

    def _release_model_turn_locked(self) -> None:
        if self._active_model_calls > 0:
            self._active_model_calls -= 1
        self._wake_waiters_locked()

    def _wake_waiters_locked(self) -> None:
        while (
            self._active_model_calls < self._policy.max_active_model_calls
            and self._waiters
        ):
            waiter = self._waiters.pop(self._next_waiter_index_locked())
            self._active_model_calls += 1
            self._record_start_locked(waiter.tenant_id)
            waiter.granted = True
            waiter.event.set()

    def _next_waiter_index_locked(self) -> int:
        if (
            self._last_started_tenant is not None
            and self._consecutive_starts >= self._policy.max_consecutive_starts
        ):
            for index, waiter in enumerate(self._waiters):
                if waiter.tenant_id != self._last_started_tenant:
                    return index
        return 0

    def _record_start_locked(self, tenant_id: str) -> None:
        if tenant_id == self._last_started_tenant:
            self._consecutive_starts += 1
            return
        self._last_started_tenant = tenant_id
        self._consecutive_starts = 1


class _Admission:
    def __init__(self, fairness: PlatformFairness, tenant_id: str) -> None:
        self._fairness = fairness
        self._tenant_id = tenant_id
        self._entered = False

    async def __aenter__(self) -> _Admission:
        await self._fairness._enter_admission(self._tenant_id)
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        if not self._entered:
            return
        self._entered = False
        await self._fairness._exit_admission(self._tenant_id)


class _ModelTurn:
    def __init__(self, fairness: PlatformFairness, tenant_id: str) -> None:
        self._fairness = fairness
        self._tenant_id = tenant_id
        self._waiter: _Waiter | None = None

    async def __aenter__(self) -> _ModelTurn:
        self._waiter = await self._fairness._enter_model_turn(self._tenant_id)
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        if self._waiter is None:
            return
        await self._fairness._exit_model_turn(self._waiter)
        self._waiter = None
