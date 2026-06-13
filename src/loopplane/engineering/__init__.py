"""LoopPlane loop-engineering layer (feature 003-loopplane-loop-engineering-layer).

The outer control loop on top of the Phase-1 runtime foundation and the Phase-2
Host Interface. It defines a loop, triggers it, starts each Agent Run **through
the Host Application Interface**, validates the outcome, optionally evaluates it,
and decides whether to stop, retry, repair, or request human review — under a
hard iteration bound — until a single terminal outcome.

It adds no runtime internals of its own: every Agent Run is started and observed
through ``loopplane.host``; the layer never reaches into Phase-1 components
(FR-080–FR-083, FR-090).
"""

from loopplane.engineering.controller import (
    LoopController,
    LoopOutcome,
    LoopTerminal,
    ReviewDecision,
    ReviewResolver,
    run_loop,
)
from loopplane.engineering.definition import (
    HostRuntimeProfile,
    InputSource,
    LoopDefinition,
    LoopDefinitionError,
    Prompt,
    StaticInput,
    validate_definition,
)
from loopplane.engineering.evaluation import EvaluationResult, Evaluator
from loopplane.engineering.events import (
    LOOP_EVENT_TYPES,
    LOOP_SCHEMA_VERSION,
    TERMINAL_LOOP_EVENTS,
    LoopEvent,
    LoopEventSink,
    LoopEventType,
)
from loopplane.engineering.policies import (
    NO_BACKOFF,
    ApprovalPolicy,
    ArtifactPolicy,
    BackoffContract,
    ConstantBackoff,
    EvaluationPolicy,
    ObservationPolicy,
    RepairContext,
    RepairInstructionSource,
    RepairPolicy,
    RetryPolicy,
    ValidationPolicy,
)
from loopplane.engineering.state import (
    ApprovalStatus,
    ArtifactRef,
    LoopState,
    RunReference,
    reconstruct_state,
)
from loopplane.engineering.stopping import (
    StopCondition,
    StopPredicate,
    max_iterations,
    stop_on_pass,
    stop_when_score_at_least,
)
from loopplane.engineering.triggers import (
    ConditionTrigger,
    IntervalTrigger,
    ManualTrigger,
    Trigger,
)
from loopplane.engineering.validation import (
    VALIDATION_STATUSES,
    NextAction,
    ValidationResult,
    ValidationStatus,
    Validator,
    decide,
)

__all__ = [
    "LOOP_EVENT_TYPES",
    "LOOP_SCHEMA_VERSION",
    "NO_BACKOFF",
    "TERMINAL_LOOP_EVENTS",
    "VALIDATION_STATUSES",
    "ApprovalPolicy",
    "ApprovalStatus",
    "ArtifactPolicy",
    "ArtifactRef",
    "BackoffContract",
    "ConditionTrigger",
    "ConstantBackoff",
    "EvaluationPolicy",
    "EvaluationResult",
    "Evaluator",
    "HostRuntimeProfile",
    "InputSource",
    "IntervalTrigger",
    "LoopController",
    "LoopDefinition",
    "LoopDefinitionError",
    "LoopEvent",
    "LoopEventSink",
    "LoopEventType",
    "LoopOutcome",
    "LoopState",
    "LoopTerminal",
    "ManualTrigger",
    "NextAction",
    "ObservationPolicy",
    "Prompt",
    "RepairContext",
    "RepairInstructionSource",
    "RepairPolicy",
    "RetryPolicy",
    "ReviewDecision",
    "ReviewResolver",
    "RunReference",
    "StaticInput",
    "StopCondition",
    "StopPredicate",
    "Trigger",
    "ValidationPolicy",
    "ValidationResult",
    "ValidationStatus",
    "Validator",
    "decide",
    "max_iterations",
    "reconstruct_state",
    "run_loop",
    "stop_on_pass",
    "stop_when_score_at_least",
    "validate_definition",
]
