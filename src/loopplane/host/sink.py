"""The host's forwarding event sink.

One stable sink object is wired into the Runtime Controller at assembly time;
the host binds the current run's consumer to it per run. It forwards every
normalized event in order (Constitution VI), captures the terminal reason for
the run's outcome, isolates a misbehaving consumer (FR-007), and — when a relay
is bound — hands approval requests to the host's approval path.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from loopplane.events import RuntimeEvent
from loopplane.events.emitter import EventSink

if TYPE_CHECKING:
    from loopplane.events.envelope import ApprovalRequestedPayload

ApprovalRelay = Callable[["ApprovalRequestedPayload"], Awaitable[None]]


class RunSink:
    """An :data:`~loopplane.events.emitter.EventSink` the host rebinds per run."""

    def __init__(self) -> None:
        self._target: EventSink | None = None
        self._relay: ApprovalRelay | None = None
        self.terminal_reason: str | None = None
        self.turns_taken: int = 0
        self.consumer_failures: list[str] = []

    def bind(
        self, target: EventSink, *, approval_relay: ApprovalRelay | None = None
    ) -> None:
        self._target = target
        self._relay = approval_relay
        self.terminal_reason = None
        self.turns_taken = 0
        self.consumer_failures = []

    def unbind(self) -> None:
        self._target = None
        self._relay = None

    async def __call__(self, event: RuntimeEvent) -> None:
        # Capture the outcome regardless of whether the consumer is healthy.
        if event.type == "run-terminated":
            self.terminal_reason = event.payload.reason
            self.turns_taken = event.payload.turns_taken

        target = self._target
        if target is not None:
            try:
                await target(event)
            except Exception as exc:  # FR-007: isolate a misbehaving consumer.
                self.consumer_failures.append(type(exc).__name__)

        # The relay resolves the pending approval; the broker is still awaiting,
        # so the resolution applied here lets the run proceed (FR-014). The relay
        # self-guards (denying on a handler error), but isolate it here too so a
        # relay bug can never crash the run.
        if event.type == "approval-requested" and self._relay is not None:
            try:
                await self._relay(event.payload)
            except Exception as exc:
                self.consumer_failures.append(type(exc).__name__)
