"""Desktop Interaction Lease and live Host Session subscriptions (078 T025/T026).

Holds at most one profile-wide interactive Host ``Session`` context. All
submit/cancel/answer traffic goes through that Host-only handle — never through
controller/gateway internals.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loopplane.events import RuntimeEvent, serialize_event
from loopplane.host import LoopPlaneHost, Session

EventEmitter = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class LiveSubscription:
    """One lease-owning interactive open bound to a Host Session context."""

    subscription_id: str
    session_id: str
    pane_id: str | None
    session: Session
    stack: AsyncExitStack
    run_active: bool = False
    released: bool = False


@dataclass
class InteractionLease:
    """Profile-wide exclusive interactive open (second open is busy)."""

    _owner: LiveSubscription | None = None
    _emit_event: EventEmitter | None = None
    _emit_outcome: EventEmitter | None = None
    _pending: dict[str, LiveSubscription] = field(default_factory=dict)

    def set_emitters(
        self,
        *,
        emit_event: EventEmitter | None = None,
        emit_outcome: EventEmitter | None = None,
    ) -> None:
        self._emit_event = emit_event
        self._emit_outcome = emit_outcome

    async def emit_outcome(self, payload: dict[str, Any]) -> None:
        if self._emit_outcome is None:
            return
        result = self._emit_outcome(payload)
        if result is not None:
            await result

    @property
    def active(self) -> LiveSubscription | None:
        return self._owner

    def get(self, subscription_id: str) -> LiveSubscription | None:
        sub = self._pending.get(subscription_id)
        if sub is None or sub.released:
            return None
        return sub

    def _reject_if_held(self) -> None:
        owner = self._owner
        if owner is not None and not owner.released:
            raise InteractionBusy(
                "interactive lease held",
                owner_pane_id=owner.pane_id,
                owner_session_id=owner.session_id,
            )

    def require_owner(self, subscription_id: str) -> LiveSubscription:
        """Only the lease-owning subscription may submit/cancel/answer."""

        sub = self.get(subscription_id)
        if sub is None:
            raise KeyError("subscription not found")
        if self._owner is not sub:
            raise InteractionBusy(
                "subscription is not the interactive lease owner",
                owner_pane_id=self._owner.pane_id if self._owner else None,
                owner_session_id=self._owner.session_id if self._owner else None,
            )
        return sub

    async def create_interactive(
        self,
        host: LoopPlaneHost,
        *,
        pane_id: str | None = None,
        working_scope: Path | None = None,
        principal_id: str | None = None,
    ) -> LiveSubscription:
        # Second acquisition fails before Host/model work when lease held.
        self._reject_if_held()

        subscription_id = str(uuid.uuid4())
        holder: dict[str, LiveSubscription] = {}
        stack = AsyncExitStack()
        await stack.__aenter__()

        async def on_event(event: RuntimeEvent) -> None:
            if self._emit_event is None:
                return
            live = holder.get("sub")
            if live is None:
                return
            payload = {
                "subscription_id": live.subscription_id,
                "session_id": live.session_id,
                "event": serialize_event(event),
            }
            result = self._emit_event(payload)
            if result is not None:
                await result

        try:
            session_cm = host.session(
                on_event,
                working_scope=working_scope,
                principal_id=principal_id,
            )
            session = await stack.enter_async_context(session_cm)
        except BaseException:
            await stack.__aexit__(None, None, None)
            raise

        sub = LiveSubscription(
            subscription_id=subscription_id,
            session_id=session.session_id,
            pane_id=pane_id,
            session=session,
            stack=stack,
        )
        holder["sub"] = sub
        self._owner = sub
        self._pending[sub.subscription_id] = sub
        return sub

    async def resume_interactive(
        self,
        host: LoopPlaneHost,
        session_id: str,
        *,
        pane_id: str | None = None,
        working_scope: Path | None = None,
        principal_id: str | None = None,
    ) -> LiveSubscription:
        self._reject_if_held()

        subscription_id = str(uuid.uuid4())
        holder: dict[str, LiveSubscription] = {}
        stack = AsyncExitStack()
        await stack.__aenter__()

        async def on_event(event: RuntimeEvent) -> None:
            if self._emit_event is None:
                return
            live = holder.get("sub")
            if live is None:
                return
            payload = {
                "subscription_id": live.subscription_id,
                "session_id": live.session_id,
                "event": serialize_event(event),
            }
            result = self._emit_event(payload)
            if result is not None:
                await result

        try:
            session_cm = host.resume_session(
                session_id,
                on_event,
                working_scope=working_scope,
                principal_id=principal_id,
            )
            session = await stack.enter_async_context(session_cm)
        except BaseException:
            await stack.__aexit__(None, None, None)
            raise

        sub = LiveSubscription(
            subscription_id=subscription_id,
            session_id=session.session_id,
            pane_id=pane_id,
            session=session,
            stack=stack,
        )
        holder["sub"] = sub
        self._owner = sub
        self._pending[sub.subscription_id] = sub
        return sub

    async def release(self, subscription_id: str) -> bool:
        sub = self._pending.get(subscription_id)
        if sub is None:
            return False
        if sub.released:
            return True
        sub.released = True
        if self._owner is sub:
            self._owner = None
        try:
            await sub.stack.__aexit__(None, None, None)
        finally:
            self._pending.pop(subscription_id, None)
        return True

    async def shutdown(self) -> None:
        """Release every interactive Host context; no new durable work after."""

        ids = list(self._pending.keys())
        for sid in ids:
            await self.release(sid)
        self._owner = None
        self._emit_event = None
        self._emit_outcome = None


class InteractionBusy(RuntimeError):
    """Second interactive open while lease is held."""

    public_code = "busy"

    def __init__(
        self,
        message: str = "interactive lease held",
        *,
        owner_pane_id: str | None = None,
        owner_session_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.owner_pane_id = owner_pane_id
        self.owner_session_id = owner_session_id
