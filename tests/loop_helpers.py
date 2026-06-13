"""Deterministic, public-safe test helpers for the loop-engineering layer
(feature 003). Credential-free: a scripted model plus scripted validators and
evaluators are the only instruments.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from loopplane.engineering import (
    EvaluationResult,
    LoopEvent,
    RunReference,
    ValidationResult,
    ValidationStatus,
)
from loopplane.engineering.policies import RepairContext
from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement


def scripted_host(*texts: str, working_scope: Path | None = None) -> LoopPlaneHost:
    """A single ``LoopPlaneHost`` over a scripted model with one text turn per
    argument. The model cursor advances across iterations, so script one turn
    per expected Agent Run."""

    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=t)]) for t in texts],
        context_capacity=100_000,
    )
    return LoopPlaneHost(RuntimeConfig(model=model), working_scope=working_scope)


def scripted_host_factory(
    *texts: str, working_scope: Path | None = None
) -> Callable[[], LoopPlaneHost]:
    """A thunk that builds a *fresh* ``LoopPlaneHost`` over a scripted model
    with one text turn per argument. A fresh host per call gives each Loop Run
    an unexhausted model, which the determinism test relies on (US1.3)."""

    def build() -> LoopPlaneHost:
        return scripted_host(*texts, working_scope=working_scope)

    return build


class ScriptedValidator:
    """Returns a sequence of validation statuses, one per iteration; repeats the
    last once exhausted."""

    def __init__(self, *statuses: ValidationStatus, reason: str | None = None) -> None:
        self._results = [
            ValidationResult(status=status, reason=reason) for status in statuses
        ]
        self.calls = 0

    def __call__(self, outcome: RunOutcome, state: object) -> ValidationResult:
        index = min(self.calls, len(self._results) - 1)
        self.calls += 1
        return self._results[index]


class ScriptedEvaluator:
    """Returns a sequence of evaluation scores, one per iteration; repeats the
    last once exhausted."""

    def __init__(self, *scores: float, label: str | None = None) -> None:
        self._results = [EvaluationResult(score=score, label=label) for score in scores]
        self.calls = 0

    def __call__(self, outcome: RunOutcome, state: object) -> EvaluationResult:
        index = min(self.calls, len(self._results) - 1)
        self.calls += 1
        return self._results[index]


class RaisingValidator:
    """A validator that always raises — exercises the fail-safe path (FR-034)."""

    def __init__(self, message: str = "validator boom") -> None:
        self.message = message

    def __call__(self, outcome: RunOutcome, state: object) -> ValidationResult:
        raise RuntimeError(self.message)


class UnknownStatusValidator:
    """Returns an unrecognized status — also fail-safe (FR-034)."""

    def __call__(self, outcome: RunOutcome, state: object) -> ValidationResult:
        return ValidationResult(status="weird")  # type: ignore[arg-type]


class RaisingEvaluator:
    """An evaluator that always raises — its error must be non-fatal (FR-043)."""

    def __call__(self, outcome: RunOutcome, state: object) -> EvaluationResult:
        raise RuntimeError("evaluator boom")


class AppendRepairInstruction:
    """A repair instruction source that references the prior failure (FR-052)."""

    PREFIX = "REPAIR:"

    def instruction(self, context: RepairContext) -> str:
        reason = context.validation_reason or "no reason given"
        return f"{self.PREFIX} fix the prior attempt ({reason})"


class LoopEventRecorder:
    """A loop event sink that records every emitted Loop Event in order."""

    def __init__(self) -> None:
        self.events: list[LoopEvent] = []

    async def __call__(self, event: LoopEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


class RunOutcomeStubHost:
    """A host-interface-shaped stub that returns pre-crafted ``RunOutcome``s.

    Used only to drive non-natural termination reasons through the Loop
    Controller (FR-016); structurally a ``LoopPlaneHost`` (duck-typed ``run``).
    """

    def __init__(self, *reasons: str) -> None:
        self._reasons = list(reasons)
        self.calls = 0

    async def run(
        self,
        prompt: object,
        on_event: object,
        *,
        on_approval: object | None = None,
        working_scope: object | None = None,
    ) -> RunOutcome:
        index = min(self.calls, len(self._reasons) - 1)
        reason = self._reasons[index]
        self.calls += 1
        return RunOutcome(
            session_id=f"stub-{self.calls}",
            termination_reason=reason,
            turns_taken=0,
            history=(),
        )

    def retrieve_artifact(self, session_id: str, reference: str) -> str | None:
        return None


def run_reference(session_id: str, reason: str = "natural-completion") -> RunReference:
    return RunReference(session_id=session_id, termination_reason=reason)
