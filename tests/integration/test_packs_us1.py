"""US1: read a run outcome and gate on a rule (spec US1; SC-001, SC-002, SC-007).

A rule-based validator reads the outcome via the shared reader, applies a host
predicate, and returns pass/fail — reading only the public surface.
"""

from __future__ import annotations

from loopplane.engineering import ValidationPolicy, ValidationResult
from loopplane.packs import OutcomeView, rule_validator
from tests.packs_helpers import scripted_outcome


def test_rule_validator_passes_when_predicate_holds() -> None:
    validator = rule_validator(lambda view: "ok" in view.final_text)
    assert validator(*scripted_outcome(text="all ok here")).status == "pass"


def test_rule_validator_fails_with_reason() -> None:
    validator = rule_validator(lambda view: False, reason="rule says no")
    result = validator(*scripted_outcome(text="x"))
    assert result.status == "fail"
    assert result.reason == "rule says no"


def test_rule_validator_fails_safe_on_a_raising_predicate() -> None:
    def boom(view: OutcomeView) -> bool:
        raise RuntimeError("predicate boom")

    result = rule_validator(boom)(*scripted_outcome(text="x"))
    assert result.status == "fail"
    assert result.reason is not None
    assert "raised" in result.reason


def test_pack_plugs_into_a_validation_policy() -> None:
    policy = ValidationPolicy(validator=rule_validator(lambda view: True))
    result = policy.validator(*scripted_outcome(text="x"))
    assert isinstance(result, ValidationResult)
    assert result.status == "pass"


def test_rule_validator_is_deterministic() -> None:
    validator = rule_validator(
        lambda view: view.terminal_reason == "natural-completion"
    )
    outcome, state = scripted_outcome(text="ok")
    assert validator(outcome, state) == validator(outcome, state)
