"""Per-principal host pool (061; gap G20-A; ADR 0009 — *pool-above-host*).

A registry that hands each principal its OWN :class:`~loopplane.host.LoopPlaneHost`
(built by a host factory, lazily created and reused), so different principals run
**concurrently** while each principal's host keeps its sequential ``_active``
invariant unchanged (a second concurrent run for the SAME principal is still
rejected by the host). Bounded by a per-principal in-flight cap + an optional
``max_principals``; per-principal isolation (one principal's host-build failure does
not corrupt another principal's entry).

The pool layers ABOVE the host: it imports :mod:`loopplane.host` only, never the
tools layer, and the ``LoopPlaneHost`` / agent loop / gateway / event contracts are
unchanged. ``create_app`` accepts a pool optionally; absent one, the web/API host
shares a single host exactly as before (byte-identical).
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import anyio

from loopplane.host import LoopPlaneHost


class TenantHostPool:
    """A per-principal ``LoopPlaneHost`` registry over a host factory (ADR 0009)."""

    def __init__(
        self,
        host_factory: Callable[..., LoopPlaneHost],
        *,
        per_principal_in_flight: int = 1,
        max_principals: int | None = None,
    ) -> None:
        if per_principal_in_flight < 1:
            raise ValueError("per_principal_in_flight must be >= 1")
        if max_principals is not None and max_principals < 1:
            raise ValueError("max_principals must be >= 1")
        self._factory = host_factory
        # A factory may take the selected model (028) or no argument.
        self._factory_takes_model = len(inspect.signature(host_factory).parameters) >= 1
        self._per_principal_in_flight = per_principal_in_flight
        self._max_principals = max_principals
        self._hosts: dict[tuple[str, str | None], LoopPlaneHost] = {}
        self._semaphores: dict[str, anyio.Semaphore] = {}

    def _principals(self) -> set[str]:
        return {principal_id for (principal_id, _model) in self._hosts}

    def _build(self, model: str | None) -> LoopPlaneHost:
        return self._factory(model) if self._factory_takes_model else self._factory()

    def host_for(self, principal_id: str, model: str | None = None) -> LoopPlaneHost:
        """The principal's host for ``model`` — lazily built then reused.

        A NEW principal beyond ``max_principals`` is rejected with a clear
        ``RuntimeError`` (bounded; no unbounded host growth). The registry is mutated
        only after a successful build, so one principal's build failure leaves every
        other principal's entry intact (per-principal isolation).
        """

        key = (principal_id, model)
        existing = self._hosts.get(key)
        if existing is not None:
            return existing
        if (
            self._max_principals is not None
            and principal_id not in self._principals()
            and len(self._principals()) >= self._max_principals
        ):
            raise RuntimeError("host pool is at capacity (max_principals)")
        host = self._build(model)
        self._hosts[key] = host
        return host

    @asynccontextmanager
    async def in_flight(self, principal_id: str) -> AsyncIterator[None]:
        """Bound a principal's concurrent in-flight runs — **reject** (not block) when
        the per-principal cap is exceeded (a clear ``RuntimeError``)."""

        semaphore = self._semaphores.setdefault(
            principal_id, anyio.Semaphore(self._per_principal_in_flight)
        )
        try:
            semaphore.acquire_nowait()
        except anyio.WouldBlock as exc:
            raise RuntimeError("principal is at its in-flight run cap") from exc
        try:
            yield
        finally:
            semaphore.release()
