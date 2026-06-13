"""The Loop Definition and its validation (contracts/loop-definition.md;
FR-001–FR-009).

A declarative, public-safe description of an outer loop. It carries no secrets
and wires no Phase-1 collaborator directly: the host runtime profile is the only
path to a composed runtime (FR-002, FR-080).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from loopplane.engineering.policies import (
    ApprovalPolicy,
    ArtifactPolicy,
    EvaluationPolicy,
    ObservationPolicy,
    RepairPolicy,
    RetryPolicy,
    ValidationPolicy,
)
from loopplane.engineering.stopping import StopCondition
from loopplane.engineering.triggers import Trigger
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ContentBlock

Prompt = str | Sequence[ContentBlock]


class LoopDefinitionError(ValueError):
    """Raised when a :class:`LoopDefinition` is invalid or internally
    inconsistent. The message is field-level and public-safe (FR-001)."""


class InputSource(Protocol):
    """Supplies the first iteration's input (FR-003). Repair augmentation is
    produced by the controller, never by mutating the source."""

    def initial(self) -> Prompt: ...


@dataclass(frozen=True)
class StaticInput:
    """A fixed first-iteration prompt — the minimal :class:`InputSource`."""

    prompt: Prompt

    def initial(self) -> Prompt:
        return self.prompt


@dataclass(frozen=True)
class HostRuntimeProfile:
    """References a Phase-2 runtime: a ``RuntimeConfig`` or a host-resolvable
    selector that builds a ``LoopPlaneHost`` (FR-002).

    Exactly one of ``config`` / ``selector`` must be present. Using a
    ``selector`` yields a fresh host per Loop Run, which a determinism test
    relies on (US1.3).
    """

    config: RuntimeConfig | None = None
    selector: Callable[[], LoopPlaneHost] | None = None

    def build(self) -> LoopPlaneHost:
        if self.selector is not None:
            return self.selector()
        if self.config is not None:
            return LoopPlaneHost(self.config)
        raise LoopDefinitionError(
            "host_profile must provide either a 'config' or a 'selector'"
        )


@dataclass(frozen=True)
class LoopDefinition:
    """The declarative outer-loop contract (FR-001)."""

    loop_id: str
    trigger: Trigger
    input_source: InputSource
    host_profile: HostRuntimeProfile
    validation_policy: ValidationPolicy
    stop_condition: StopCondition
    retry_policy: RetryPolicy = RetryPolicy()
    repair_policy: RepairPolicy = RepairPolicy()
    artifact_policy: ArtifactPolicy = ArtifactPolicy()
    approval_policy: ApprovalPolicy = ApprovalPolicy()
    observation_policy: ObservationPolicy = ObservationPolicy()
    evaluation_policy: EvaluationPolicy | None = None


def validate_definition(definition: LoopDefinition) -> None:
    """Fail fast on an invalid or inconsistent Loop Definition (FR-001, FR-013).

    Raises :class:`LoopDefinitionError` before any Loop Run starts.
    """

    if not definition.loop_id:
        raise LoopDefinitionError("loop_id must be a non-empty string")

    profile = definition.host_profile
    if profile.config is None and profile.selector is None:
        raise LoopDefinitionError(
            "host_profile must provide either a 'config' or a 'selector'"
        )
    if profile.config is not None and profile.selector is not None:
        raise LoopDefinitionError(
            "host_profile must provide exactly one of 'config' or 'selector'"
        )

    if definition.stop_condition.max_iterations < 1:
        raise LoopDefinitionError(
            "stop_condition.max_iterations must be at least 1 to guarantee termination"
        )

    repair = definition.repair_policy
    if repair.enabled and repair.instruction_source is None:
        raise LoopDefinitionError(
            "repair_policy is enabled but no instruction_source is provided"
        )
