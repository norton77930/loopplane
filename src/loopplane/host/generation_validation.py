"""Public non-instance active-generation validator (078 T025).

``validate_active_generation`` proves pristine absence or initialized
current-state consistency **without** constructing ``LoopPlaneHost``, opening
normal stores, mutating the filesystem, or returning live storage handles.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

GenerationState = Literal["absent_uninitialized", "initialized"]


@dataclass(frozen=True, slots=True)
class GenerationExpectation:
    """What the caller expects for checkpoint/artifact generation state."""

    checkpoint_state: GenerationState = "absent_uninitialized"
    artifact_state: GenerationState = "absent_uninitialized"
    schema_version: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationValidationResult:
    """Bounded, public-safe validation outcome (no store handles or paths)."""

    ok: bool
    checkpoint_state: GenerationState | Literal["unexpected"]
    artifact_state: GenerationState | Literal["unexpected"]
    reason: str | None = None


class GenerationStateProvider(Protocol):
    """Read-only probe used by the validator (injected in tests)."""

    def probe(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a mapping with checkpoint_state / artifact_state keys."""
        ...


def _generation_state(value: str) -> GenerationState | None:
    if value == "absent_uninitialized":
        return "absent_uninitialized"
    if value == "initialized":
        return "initialized"
    return None


class _DefaultAbsentProvider:
    """Default Host-owned provider: empty/missing source => absent_uninitialized."""

    def probe(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
        if not source:
            return {
                "checkpoint_state": "absent_uninitialized",
                "artifact_state": "absent_uninitialized",
            }
        return {
            "checkpoint_state": source.get("checkpoint_state", "absent_uninitialized"),
            "artifact_state": source.get("artifact_state", "absent_uninitialized"),
            "schema_version": source.get("schema_version"),
            "unexpected": source.get("unexpected", False),
        }


def validate_active_generation(
    source: Mapping[str, Any] | None,
    expectation: GenerationExpectation,
    *,
    provider: GenerationStateProvider | None = None,
) -> GenerationValidationResult:
    """Validate generation absence or current-state consistency.

    Guarantees:
    - zero ``LoopPlaneHost`` / normal-store construction
    - zero filesystem creation/mutation by this function
    - no returned storage handle or path
    """

    probe: GenerationStateProvider = provider or _DefaultAbsentProvider()
    try:
        observed = probe.probe(dict(source or {}))
    except Exception as exc:  # noqa: BLE001 — public-safe containment
        return GenerationValidationResult(
            ok=False,
            checkpoint_state="unexpected",
            artifact_state="unexpected",
            reason=f"provider_fault:{type(exc).__name__}",
        )

    if observed.get("unexpected"):
        return GenerationValidationResult(
            ok=False,
            checkpoint_state="unexpected",
            artifact_state="unexpected",
            reason="unexpected_payload",
        )

    ck = _generation_state(
        str(observed.get("checkpoint_state", "absent_uninitialized"))
    )
    ak = _generation_state(str(observed.get("artifact_state", "absent_uninitialized")))
    if ck is None:
        return GenerationValidationResult(
            ok=False,
            checkpoint_state="unexpected",
            artifact_state=ak or "unexpected",
            reason="invalid_checkpoint_state",
        )
    if ak is None:
        return GenerationValidationResult(
            ok=False,
            checkpoint_state=ck,
            artifact_state="unexpected",
            reason="invalid_artifact_state",
        )

    if ck != expectation.checkpoint_state or ak != expectation.artifact_state:
        return GenerationValidationResult(
            ok=False,
            checkpoint_state=ck,
            artifact_state=ak,
            reason="expectation_mismatch",
        )

    if expectation.schema_version is not None:
        obs_ver = observed.get("schema_version")
        if obs_ver != expectation.schema_version:
            return GenerationValidationResult(
                ok=False,
                checkpoint_state=ck,
                artifact_state=ak,
                reason="schema_version_mismatch",
            )

    return GenerationValidationResult(
        ok=True,
        checkpoint_state=ck,
        artifact_state=ak,
        reason=None,
    )
