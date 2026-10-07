"""Validator packs (contracts/packs.md; FR-010–FR-014).

Reusable implementations of the Phase-3 Validator Protocol. Each is a pure
callable that reads the outcome through the shared reader and returns a
``ValidationResult``. Every validator fails safe — malformed or missing input
maps to an explicit ``fail`` with a reason, never a silent ``pass``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

import jsonschema

from loopplane.engineering import ValidationResult
from loopplane.packs.reader import OutcomeView, read_outcome

if TYPE_CHECKING:
    from loopplane.engineering import LoopState, Validator
    from loopplane.host import RunOutcome


class PackConfigError(ValueError):
    """Raised at construction for an invalid pack configuration (FR-011).

    Public-safe; never carries a secret or a private path (NFR-004).
    """


def rule_validator(
    predicate: Callable[[OutcomeView], bool], *, reason: str = "rule not satisfied"
) -> Validator:
    """`pass` when the host predicate over the outcome view is true, else `fail`
    (FR-010). A raising predicate fails safe to `fail` (FR-014)."""

    def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        view = read_outcome(outcome, state)
        try:
            satisfied = predicate(view)
        except Exception:  # noqa: BLE001 - fail safe; never echo the exception
            return ValidationResult(status="fail", reason="rule raised")
        if satisfied:
            return ValidationResult(status="pass")
        return ValidationResult(status="fail", reason=reason)

    return validate


TextMode = Literal["matches", "contains", "not_contains"]


def text_validator(
    *, mode: TextMode, pattern: str, reason: str | None = None
) -> Validator:
    """Check the final assistant text against a regex (FR-011). The pattern is
    compiled at construction; an invalid pattern raises ``PackConfigError``."""

    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise PackConfigError(f"invalid regex pattern: {exc}") from exc

    def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        text = read_outcome(outcome, state).final_text
        if mode == "matches":
            ok = compiled.fullmatch(text) is not None
        elif mode == "contains":
            ok = compiled.search(text) is not None
        else:
            ok = compiled.search(text) is None
        if ok:
            return ValidationResult(status="pass")
        return ValidationResult(
            status="fail", reason=reason or f"text {mode} {pattern!r} failed"
        )

    return validate


def json_schema_validator(*, schema: Mapping[str, Any]) -> Validator:
    """The final output MUST parse as JSON and validate against ``schema``
    (FR-012). Unparseable JSON fails safe to `fail` with a reason (FR-014)."""

    schema_dict = dict(schema)

    def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        text = read_outcome(outcome, state).final_text
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            return ValidationResult(
                status="fail", reason=f"output is not valid JSON: {exc}"
            )
        try:
            jsonschema.validate(data, schema_dict)
        except jsonschema.ValidationError as exc:
            return ValidationResult(
                status="fail", reason=f"schema violation: {exc.message}"
            )
        return ValidationResult(status="pass")

    return validate


def artifact_presence_validator(*, require: bool = True) -> Validator:
    """`require=True` ⇒ `pass` iff the run produced an artifact reference;
    `require=False` ⇒ `pass` iff it produced none (FR-013)."""

    def validate(outcome: RunOutcome, state: LoopState) -> ValidationResult:
        has_artifact = len(read_outcome(outcome, state).artifact_references) > 0
        if require == has_artifact:
            return ValidationResult(status="pass")
        reason = (
            "expected an artifact but none was produced"
            if require
            else "expected no artifact but one was produced"
        )
        return ValidationResult(status="fail", reason=reason)

    return validate
