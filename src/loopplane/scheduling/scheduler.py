"""The Scheduler (contracts/scheduler.md; FR-001–FR-004, FR-020–FR-073).

A local, in-process scheduler that owns a trigger registry and an injectable
Clock and starts every Scheduled Loop Run **only** through the Phase-3 `run_loop`
entry point. It decides *when* a trigger fires — manual on demand, interval per
period, or condition on a satisfied predicate — applies the missed-run policy,
records reference-only Trigger State, and emits the distinct Scheduler Event
stream. It serializes the Loop Runs it starts (one in flight at a time) and never
reaches into a Phase-1/2/3 internal (FR-002, FR-072, FR-090).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loopplane.engineering import run_loop
from loopplane.scheduling.clock import Clock
from loopplane.scheduling.events import (
    SchedulerEvent,
    SchedulerEventSink,
    SchedulerEventType,
)
from loopplane.scheduling.policy import ConditionMode, MissedRunPolicy, SchedulerError
from loopplane.scheduling.registry import (
    Predicate,
    TriggerRegistration,
    validate_registration,
)
from loopplane.scheduling.state import LoopRunRef, TriggerState

if TYPE_CHECKING:
    from loopplane.engineering import LoopDefinition, LoopOutcome

_MISSED_EVENT: dict[MissedRunPolicy, SchedulerEventType] = {
    "skip": "run_skipped",
    "catch_up_once": "run_caught_up",
    "coalesce": "run_coalesced",
}


class Scheduler:
    """Owns the trigger registry and the Clock; fires Loop Runs via `run_loop`."""

    def __init__(
        self, clock: Clock, *, on_event: SchedulerEventSink | None = None
    ) -> None:
        self._clock = clock
        self._on_event = on_event
        self._registry: dict[str, TriggerRegistration] = {}
        self._states: dict[str, TriggerState] = {}
        self._events: list[SchedulerEvent] = []
        self._pending: list[SchedulerEvent] = []
        self._sequence = 0
        self._running = True
        self._in_flight = False

    # --- Registration (FR-001, FR-004) ---

    def register_manual(self, trigger_id: str, definition: LoopDefinition) -> None:
        self._register(TriggerRegistration(trigger_id, definition, kind="manual"))

    def register_interval(
        self,
        trigger_id: str,
        definition: LoopDefinition,
        *,
        interval_seconds: float,
        start_immediately: bool = False,
        missed_run_policy: MissedRunPolicy = "skip",
    ) -> None:
        self._register(
            TriggerRegistration(
                trigger_id,
                definition,
                kind="interval",
                interval_seconds=interval_seconds,
                start_immediately=start_immediately,
                missed_run_policy=missed_run_policy,
            )
        )

    def register_condition(
        self,
        trigger_id: str,
        definition: LoopDefinition,
        *,
        predicate: Predicate,
        mode: ConditionMode = "edge",
    ) -> None:
        self._register(
            TriggerRegistration(
                trigger_id, definition, kind="condition", predicate=predicate, mode=mode
            )
        )

    def _register(self, registration: TriggerRegistration) -> None:
        validate_registration(registration, set(self._registry))
        self._registry[registration.trigger_id] = registration
        state = TriggerState(trigger_id=registration.trigger_id)
        if registration.kind == "interval":
            assert registration.interval_seconds is not None
            now = self._clock.now()
            state.next_due = (
                now
                if registration.start_immediately
                else now + registration.interval_seconds
            )
        self._states[registration.trigger_id] = state
        self._emit(
            "trigger_registered",
            trigger_id=registration.trigger_id,
            payload={"kind": registration.kind, "next_due": state.next_due},
        )

    def unregister(self, trigger_id: str) -> None:
        self._require(trigger_id)
        del self._registry[trigger_id]
        del self._states[trigger_id]

    # --- Lifecycle (FR-070–FR-071) ---

    def pause(self, trigger_id: str) -> None:
        self._require(trigger_id)
        self._states[trigger_id].enabled = False
        self._emit("trigger_paused", trigger_id=trigger_id)

    def resume(self, trigger_id: str) -> None:
        self._require(trigger_id)
        self._states[trigger_id].enabled = True
        self._emit("trigger_resumed", trigger_id=trigger_id)

    def stop(self) -> None:
        self._running = False
        self._emit("scheduler_stopped")

    async def drain(self) -> None:
        # Runs are serialized (await-per-fire), so at most one is ever in flight
        # and there is nothing to join: stop starting new runs and finish.
        self._running = False
        self._emit("scheduler_stopped")
        await self._flush()

    # --- Firing (FR-002, FR-020, FR-030–FR-040) ---

    async def start(self, trigger_id: str) -> LoopOutcome:
        """Manually fire a registered trigger once, on demand (US1)."""

        self._require(trigger_id)
        if not self._running:
            raise SchedulerError("scheduler is stopped; start nothing")
        outcome = await self._fire(self._registry[trigger_id])
        await self._flush()
        return outcome

    async def poll(self) -> list[LoopOutcome]:
        """Fire every due interval trigger and every satisfied condition trigger
        against the current Clock time, in registration order (FR-073)."""

        outcomes: list[LoopOutcome] = []
        if not self._running:
            await self._flush()
            return outcomes
        now = self._clock.now()
        for trigger_id in list(self._registry):
            registration = self._registry[trigger_id]
            state = self._states[trigger_id]
            if not state.enabled or registration.kind == "manual":
                continue
            if registration.kind == "interval":
                outcome = await self._poll_interval(registration, state, now)
            else:
                outcome = await self._poll_condition(registration, state, now)
            if outcome is not None:
                outcomes.append(outcome)
        await self._flush()
        return outcomes

    async def _poll_interval(
        self, registration: TriggerRegistration, state: TriggerState, now: float
    ) -> LoopOutcome | None:
        period = registration.interval_seconds
        assert period is not None
        next_due = state.next_due
        if next_due is None or now < next_due:
            return None  # not due (also handles a backward clock move)

        ticks = int((now - next_due) // period) + 1  # due ticks at/under now
        missed = ticks - 1
        policy = registration.missed_run_policy
        if policy == "coalesce":
            new_next_due = now + period
        else:  # skip / catch_up_once advance past the jump
            new_next_due = next_due + ticks * period
        if missed > 0:
            self._emit(
                _MISSED_EVENT[policy],
                trigger_id=registration.trigger_id,
                payload={"missed_ticks": missed, "next_due": new_next_due},
            )
        return await self._fire(
            registration, missed_ticks_delta=missed, next_due=new_next_due
        )

    async def _poll_condition(
        self, registration: TriggerRegistration, state: TriggerState, now: float
    ) -> LoopOutcome | None:
        assert registration.predicate is not None
        try:
            result = registration.predicate()
            value = result if isinstance(result, bool) else await result
        except Exception as exc:  # noqa: BLE001 - non-fatal diagnostic (FR-042)
            self._emit(
                "condition_error",
                trigger_id=registration.trigger_id,
                payload={"error": repr(exc)},
            )
            return None
        previous = state.last_condition_value
        state.last_condition_value = value
        fire = value if registration.mode == "level" else (value and not previous)
        if not fire:
            return None
        return await self._fire(registration, condition_value=value)

    async def _fire(
        self,
        registration: TriggerRegistration,
        *,
        missed_ticks_delta: int = 0,
        next_due: float | None = None,
        condition_value: bool | None = None,
    ) -> LoopOutcome:
        if self._in_flight:
            raise SchedulerError(
                "a Scheduled Loop Run is already in flight; runs are serialized"
            )
        self._in_flight = True
        try:
            outcome = await run_loop(registration.definition)
        finally:
            self._in_flight = False

        state = self._states[registration.trigger_id]
        state.fire_count += 1
        state.last_fired = self._clock.now()
        state.missed_ticks += missed_ticks_delta
        if registration.kind == "interval":
            state.next_due = next_due
        state.last_run_ref = LoopRunRef(
            trigger_id=registration.trigger_id,
            terminal_event=outcome.terminal_event,
            paused=outcome.paused,
        )
        payload: dict[str, Any] = {
            "kind": registration.kind,
            "next_due": state.next_due,
            "missed_ticks_delta": missed_ticks_delta,
            "terminal_event": outcome.terminal_event,
            "paused": outcome.paused,
        }
        if condition_value is not None:
            payload["condition_value"] = condition_value
        self._emit("trigger_fired", trigger_id=registration.trigger_id, payload=payload)
        return outcome

    # --- Inspection ---

    def trigger_state(self, trigger_id: str) -> TriggerState:
        self._require(trigger_id)
        return self._states[trigger_id]

    def trigger_ids(self) -> tuple[str, ...]:
        return tuple(self._registry)

    @property
    def events(self) -> tuple[SchedulerEvent, ...]:
        return tuple(self._events)

    # --- Internals ---

    def _require(self, trigger_id: str) -> None:
        if trigger_id not in self._registry:
            raise SchedulerError(f"unknown trigger id: {trigger_id!r}")

    def _emit(
        self,
        event_type: SchedulerEventType,
        *,
        trigger_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = SchedulerEvent(
            type=event_type,
            sequence=self._sequence,
            clock_time=self._clock.now(),
            trigger_id=trigger_id,
            payload=payload or {},
        )
        self._sequence += 1
        self._events.append(event)
        if self._on_event is not None:
            self._pending.append(event)

    async def _flush(self) -> None:
        if self._on_event is None:
            return
        pending = self._pending
        self._pending = []
        for event in pending:
            await self._on_event(event)
