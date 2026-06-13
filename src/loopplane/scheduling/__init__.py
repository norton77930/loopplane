"""LoopPlane scheduler & trigger engine (feature 004).

A local, in-process scheduler that makes the Phase-3 interval and condition
trigger contracts executable. A ``Scheduler`` owns a registry of triggers and an
injectable ``Clock`` and starts every Scheduled Loop Run **only** through the
Phase-3 ``run_loop`` entry point — never bypassing the loop layer or reaching
into Phase-1/2/3 internals (FR-002, FR-090).
"""

from loopplane.scheduling.clock import Clock, RealClock, VirtualClock
from loopplane.scheduling.events import (
    SCHEDULER_EVENT_TYPES,
    SCHEDULER_SCHEMA_VERSION,
    SchedulerEvent,
    SchedulerEventSink,
    SchedulerEventType,
)
from loopplane.scheduling.policy import (
    ConditionMode,
    MissedRunPolicy,
    SchedulerError,
)
from loopplane.scheduling.registry import (
    Predicate,
    TriggerKind,
    TriggerRegistration,
    validate_registration,
)
from loopplane.scheduling.scheduler import Scheduler
from loopplane.scheduling.state import (
    LoopRunRef,
    TriggerState,
    reconstruct_states,
)

__all__ = [
    "SCHEDULER_EVENT_TYPES",
    "SCHEDULER_SCHEMA_VERSION",
    "Clock",
    "ConditionMode",
    "LoopRunRef",
    "MissedRunPolicy",
    "Predicate",
    "RealClock",
    "Scheduler",
    "SchedulerError",
    "SchedulerEvent",
    "SchedulerEventSink",
    "SchedulerEventType",
    "TriggerKind",
    "TriggerRegistration",
    "TriggerState",
    "VirtualClock",
    "reconstruct_states",
    "validate_registration",
]
