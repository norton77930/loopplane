"""The Loop Controller and the Loop Run lifecycle
(contracts/loop-controller.md; FR-010–FR-016, FR-032, FR-050–FR-056).

The Loop Controller owns a Loop Run: it starts each Agent Run **through the
Phase-2 Host Application Interface**, applies the Validator and optional
Evaluator, decides the next action, records reference-only Loop State, and emits
the distinct Loop Event stream — under a hard iteration bound, until a single
terminal outcome. It never drives a session directly and never reaches into a
Phase-1 internal (FR-080–FR-083, FR-090).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from loopplane.engineering.definition import (
    LoopDefinition,
    Prompt,
    validate_definition,
)
from loopplane.engineering.evaluation import EvaluationResult
from loopplane.engineering.events import LoopEvent, LoopEventSink, LoopEventType
from loopplane.engineering.policies import RepairContext
from loopplane.engineering.state import ArtifactRef, LoopState, RunReference
from loopplane.engineering.validation import (
    VALIDATION_STATUSES,
    ValidationResult,
    decide,
)
from loopplane.events import RuntimeEvent, ToolCallCompletedEvent
from loopplane.model import ContentBlock, TextBlock

if TYPE_CHECKING:
    from loopplane.host import LoopPlaneHost, RunOutcome
    from loopplane.host.host import OnApproval

LoopTerminal = Literal["loop_completed", "loop_failed"]


@dataclass(frozen=True)
class ReviewDecision:
    """An external human-review decision supplied to the loop (US5; FR-082)."""

    approve: bool
    reason: str | None = None


# A host-supplied resolver that turns a paused human-review request into a
# decision in-process. When absent, the loop pauses and returns pending — it
# starts no further Agent Run until a decision is supplied (US5.4).
ReviewResolver = Callable[[LoopState], "ReviewDecision | Awaitable[ReviewDecision]"]


@dataclass(frozen=True)
class LoopOutcome:
    """What a Loop Run returns: its terminal Loop Event (or ``None`` when paused
    for human review), the stop reason, the final Loop State, the ordered Loop
    Event stream, and any non-fatal diagnostics (FR-074)."""

    loop_id: str
    loop_definition_id: str
    terminal_event: LoopTerminal | None
    stop_reason: str | None
    state: LoopState
    events: tuple[LoopEvent, ...]
    diagnostics: tuple[str, ...] = ()

    @property
    def paused(self) -> bool:
        """True when the Loop Run is suspended pending a human-review decision
        (no terminal Loop Event emitted yet)."""

        return self.terminal_event is None


class LoopController:
    """Owns one Loop Run's lifecycle (FR-010)."""

    def __init__(
        self,
        definition: LoopDefinition,
        *,
        on_loop_event: LoopEventSink | None = None,
        on_approval: OnApproval | None = None,
        review_resolver: ReviewResolver | None = None,
    ) -> None:
        validate_definition(definition)
        self._definition = definition
        self._on_loop_event = on_loop_event
        self._on_approval = on_approval
        self._review_resolver = review_resolver
        self._host: LoopPlaneHost = definition.host_profile.build()
        self._state = LoopState(
            loop_id=definition.loop_id, loop_definition_id=definition.loop_id
        )
        self._events: list[LoopEvent] = []
        self._diagnostics: list[str] = []
        self._sequence = 0
        self._retries_used = 0

    async def run(self) -> LoopOutcome:
        definition = self._definition
        stop = definition.stop_condition
        retry = definition.retry_policy

        await self._emit("loop_started")
        current_input: Prompt = definition.input_source.initial()
        kind: Literal["initial", "retry", "repair"] = "initial"

        while True:
            next_index = self._state.iteration_index + 1
            if next_index > stop.max_iterations:
                return await self._terminate(
                    "loop_failed",
                    f"iteration bound of {stop.max_iterations} reached",
                )
            self._state.iteration_index = next_index
            await self._emit(
                "loop_iteration_started",
                iteration_index=next_index,
                payload={"kind": kind},
            )

            outcome, artifacts = await self._start_agent_run(current_input)
            self._state.run_refs += (
                RunReference(outcome.session_id, outcome.termination_reason),
            )
            self._state.artifacts += tuple(artifacts)
            await self._emit(
                "loop_iteration_completed",
                iteration_index=next_index,
                session_id=outcome.session_id,
                payload={"termination_reason": outcome.termination_reason},
            )

            # FR-016: a non-natural terminal reason is a failed iteration subject
            # to the retry policy — never a loop crash, and never validated.
            if outcome.termination_reason != "natural-completion":
                self._diagnostics.append(
                    f"agent run terminated non-naturally: {outcome.termination_reason}"
                )
                decision = self._fail_decision()
                if decision == "retry":
                    await self._schedule_retry(next_index, outcome.session_id)
                    kind = "retry"
                    continue
                return await self._terminate(
                    "loop_failed",
                    f"non-natural termination: {outcome.termination_reason}",
                )

            validation = await self._validate(outcome)
            if validation is None:
                return await self._fail_safe(next_index, outcome.session_id)
            self._state.latest_validation = validation
            await self._emit(
                "validation_completed",
                iteration_index=next_index,
                session_id=outcome.session_id,
                payload={"status": validation.status, "reason": validation.reason},
            )

            if definition.evaluation_policy is not None:
                await self._evaluate(outcome, next_index)

            action = decide(
                validation.status,
                retries_used=self._retries_used,
                max_retries=retry.max_retries,
                stop_satisfied=stop.satisfied(self._state),
            )

            if action == "stop_success":
                return await self._terminate(
                    "loop_completed", validation.reason or "stop condition satisfied"
                )
            if action == "stop_failure":
                return await self._terminate(
                    "loop_failed", validation.reason or "validation failed"
                )
            if action == "continue":
                current_input = definition.input_source.initial()
                kind = "initial"
                self._retries_used = 0
                continue
            if action == "retry":
                await self._schedule_retry(next_index, outcome.session_id)
                kind = "retry"
                continue
            if action == "repair":
                current_input = await self._request_repair(
                    next_index, outcome, validation
                )
                kind = "repair"
                self._retries_used = 0
                continue
            # action == "human_review"
            paused = await self._request_human_review(
                next_index, outcome.session_id, cause="validator_status"
            )
            if paused is not None:
                return paused

    # --- Agent Run invocation (host-only; FR-080–FR-083) ---

    async def _start_agent_run(
        self, prompt: Prompt
    ) -> tuple[RunOutcome, list[ArtifactRef]]:
        artifacts: list[ArtifactRef] = []

        async def sink(event: RuntimeEvent) -> None:
            if (
                isinstance(event, ToolCallCompletedEvent)
                and event.payload.artifact_reference is not None
            ):
                artifacts.append(
                    ArtifactRef(
                        session_id=event.session_id,
                        reference=event.payload.artifact_reference,
                    )
                )

        outcome = await self._host.run(prompt, sink, on_approval=self._on_approval)
        return outcome, artifacts

    # --- Validation / evaluation ---

    async def _validate(self, outcome: RunOutcome) -> ValidationResult | None:
        """Apply the Validator; return ``None`` to signal the fail-safe path
        (a raised or unrecognized status; FR-034)."""

        validator = self._definition.validation_policy.validator
        try:
            result = validator(outcome, self._state)
            validation = (
                result if isinstance(result, ValidationResult) else await result
            )
        except Exception as exc:  # noqa: BLE001 - fail safe, never a silent pass
            self._diagnostics.append(f"validator raised: {exc!r}")
            return None
        if validation.status not in VALIDATION_STATUSES:
            self._diagnostics.append(
                f"validator returned unrecognized status: {validation.status!r}"
            )
            return None
        return validation

    async def _evaluate(self, outcome: RunOutcome, iteration_index: int) -> None:
        policy = self._definition.evaluation_policy
        assert policy is not None
        try:
            result = policy.evaluator(outcome, self._state)
            evaluation = (
                result if isinstance(result, EvaluationResult) else await result
            )
        except Exception as exc:  # noqa: BLE001 - non-fatal diagnostic (FR-043)
            self._diagnostics.append(f"evaluator raised: {exc!r}")
            return
        self._state.latest_evaluation = evaluation
        await self._emit(
            "evaluation_completed",
            iteration_index=iteration_index,
            session_id=outcome.session_id,
            payload={
                "score": evaluation.score,
                "label": evaluation.label,
                "reason": evaluation.reason,
            },
        )

    # --- Retry / repair (FR-050–FR-056) ---

    def _fail_decision(self) -> Literal["retry", "stop_failure"]:
        retry = self._definition.retry_policy
        return "retry" if self._retries_used < retry.max_retries else "stop_failure"

    async def _schedule_retry(self, iteration_index: int, session_id: str) -> None:
        self._retries_used += 1
        delay = self._definition.retry_policy.backoff.delay_seconds(self._retries_used)
        await self._emit(
            "retry_scheduled",
            iteration_index=iteration_index,
            session_id=session_id,
            payload={"attempt": self._retries_used, "delay_seconds": delay},
        )

    async def _request_repair(
        self, iteration_index: int, outcome: RunOutcome, validation: ValidationResult
    ) -> Prompt:
        await self._emit(
            "repair_requested",
            iteration_index=iteration_index,
            session_id=outcome.session_id,
            payload={"reason": validation.reason},
        )
        return self._build_repair_input(outcome, validation)

    def _build_repair_input(
        self, outcome: RunOutcome, validation: ValidationResult
    ) -> Prompt:
        """Inject the repair instruction and previous-run context into a new
        input, without mutating the Loop Definition (FR-052)."""

        policy = self._definition.repair_policy
        prior = RunReference(outcome.session_id, outcome.termination_reason)
        reused = self._state.artifacts if self._definition.artifact_policy.reuse else ()
        context = RepairContext(
            prior_run=prior,
            validation_reason=validation.reason,
            validation_metadata=validation.metadata,
            reused_artifacts=reused,
        )
        instruction = (
            policy.instruction_source.instruction(context)
            if policy.instruction_source is not None
            else "Repair the previous attempt."
        )
        original = self._definition.input_source.initial()
        suffix = (
            f"{instruction}\n"
            f"[prior-run {prior.session_id} ({prior.termination_reason}); "
            f"reason: {validation.reason}; metadata: {dict(validation.metadata)}]"
        )
        if reused:
            suffix += (
                "\n[reused-artifacts: " + ", ".join(a.reference for a in reused) + "]"
            )
        return _augment(original, suffix)

    # --- Human review (FR-009, FR-034, US5) ---

    async def _request_human_review(
        self, iteration_index: int, session_id: str, *, cause: str
    ) -> LoopOutcome | None:
        await self._emit(
            "human_review_requested",
            iteration_index=iteration_index,
            session_id=session_id,
            payload={"cause": cause},
        )
        if self._review_resolver is None:
            # Pause: start no further Agent Run until a decision is supplied.
            self._state.approval_status = "pending"
            return self._paused()
        raw = self._review_resolver(self._state)
        decision = raw if isinstance(raw, ReviewDecision) else await raw
        if decision.approve:
            self._state.approval_status = "approved"
            return await self._terminate(
                "loop_completed", decision.reason or "approved by human review"
            )
        self._state.approval_status = "rejected"
        return await self._terminate(
            "loop_failed", decision.reason or "rejected by human review"
        )

    async def _fail_safe(self, iteration_index: int, session_id: str) -> LoopOutcome:
        """Route a validator fault to human review, or to ``loop_failed`` when
        review is unavailable — never a silent pass (FR-034)."""

        if self._definition.approval_policy.human_review_available:
            paused = await self._request_human_review(
                iteration_index, session_id, cause="fail_safe"
            )
            if paused is not None:
                return paused
            # A resolver decided; the loop already terminated. Unreachable here
            # because _request_human_review returns a terminal outcome when a
            # resolver is present.
        return await self._terminate(
            "loop_failed", "validator failed safe; human review unavailable"
        )

    # --- Terminal helpers ---

    async def _terminate(self, terminal: LoopTerminal, reason: str) -> LoopOutcome:
        self._state.stop_reason = reason
        await self._emit(terminal, payload={"stop_reason": reason})
        return LoopOutcome(
            loop_id=self._definition.loop_id,
            loop_definition_id=self._definition.loop_id,
            terminal_event=terminal,
            stop_reason=reason,
            state=self._state,
            events=tuple(self._events),
            diagnostics=tuple(self._diagnostics),
        )

    def _paused(self) -> LoopOutcome:
        return LoopOutcome(
            loop_id=self._definition.loop_id,
            loop_definition_id=self._definition.loop_id,
            terminal_event=None,
            stop_reason=None,
            state=self._state,
            events=tuple(self._events),
            diagnostics=tuple(self._diagnostics),
        )

    async def _emit(
        self,
        event_type: LoopEventType,
        *,
        iteration_index: int | None = None,
        session_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = LoopEvent(
            type=event_type,
            sequence=self._sequence,
            loop_id=self._definition.loop_id,
            loop_definition_id=self._definition.loop_id,
            iteration_index=iteration_index,
            session_id=session_id,
            payload=payload or {},
        )
        self._sequence += 1
        self._events.append(event)
        # Observation defaults off; emission to an external sink changes nothing
        # about the decisions or the terminal outcome (NFR-005, SC-009).
        if self._definition.observation_policy.emit_loop_events and (
            self._on_loop_event is not None
        ):
            await self._on_loop_event(event)


def _augment(original: Prompt, suffix: str) -> Prompt:
    if isinstance(original, str):
        return f"{original}\n\n{suffix}"
    blocks: list[ContentBlock] = list(original)
    blocks.append(TextBlock(text=suffix))
    return blocks


async def run_loop(
    definition: LoopDefinition,
    *,
    on_loop_event: LoopEventSink | None = None,
    on_approval: OnApproval | None = None,
    review_resolver: ReviewResolver | None = None,
) -> LoopOutcome:
    """Start one Loop Run for ``definition`` and drive it to a terminal outcome
    (or a human-review pause). This is the manual entry point a host calls
    directly, and the same entry a host driver uses to enact an interval or
    condition trigger (FR-020–FR-022, SC-008).
    """

    controller = LoopController(
        definition,
        on_loop_event=on_loop_event,
        on_approval=on_approval,
        review_resolver=review_resolver,
    )
    return await controller.run()
