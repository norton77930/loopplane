"""US5: validate artifacts and keep edges honest (spec US5; SC-003, SC-008).

The artifact-presence validator and every pack's fail-safe behavior on a
degenerate outcome.
"""

from __future__ import annotations

from loopplane.packs import (
    artifact_presence_validator,
    json_schema_validator,
    length_evaluator,
    text_validator,
)
from tests.packs_helpers import SAMPLE_SCHEMA, scripted_outcome


def test_artifact_required_present_or_absent() -> None:
    validator = artifact_presence_validator(require=True)
    assert validator(*scripted_outcome(text="x", artifacts=("a/1",))).status == "pass"
    assert validator(*scripted_outcome(text="x")).status == "fail"


def test_artifact_must_not_produce() -> None:
    validator = artifact_presence_validator(require=False)
    assert validator(*scripted_outcome(text="x")).status == "pass"
    assert validator(*scripted_outcome(text="x", artifacts=("a/1",))).status == "fail"


def test_every_pack_fails_safe_on_a_degenerate_outcome() -> None:
    empty = scripted_outcome(text="")  # no assistant text, no artifacts

    assert text_validator(mode="contains", pattern="x")(*empty).status == "fail"
    assert json_schema_validator(schema=SAMPLE_SCHEMA)(*empty).status == "fail"
    assert artifact_presence_validator(require=True)(*empty).status == "fail"
    # The length evaluator degrades to a 0.0 score, never a crash.
    assert length_evaluator(target_chars=10)(*empty).score == 0.0
