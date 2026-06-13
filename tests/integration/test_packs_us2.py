"""US2: validate text and structured output (spec US2; SC-003, SC-008).

Text/regex and JSON-schema validators return pass/fail with reasons and fail
safe on malformed input.
"""

from __future__ import annotations

import pytest

from loopplane.packs import PackConfigError, json_schema_validator, text_validator
from tests.packs_helpers import SAMPLE_SCHEMA, scripted_outcome


def test_text_contains() -> None:
    validator = text_validator(mode="contains", pattern="done")
    assert validator(*scripted_outcome(text="all done")).status == "pass"
    assert validator(*scripted_outcome(text="nope")).status == "fail"


def test_text_matches_full_string() -> None:
    validator = text_validator(mode="matches", pattern=r"\d+")
    assert validator(*scripted_outcome(text="123")).status == "pass"
    assert validator(*scripted_outcome(text="12a")).status == "fail"


def test_text_not_contains() -> None:
    validator = text_validator(mode="not_contains", pattern="error")
    assert validator(*scripted_outcome(text="all good")).status == "pass"
    assert validator(*scripted_outcome(text="an error occurred")).status == "fail"


def test_invalid_regex_rejected_at_construction() -> None:
    with pytest.raises(PackConfigError, match="invalid regex"):
        text_validator(mode="contains", pattern="[")


def test_json_schema_passes_valid_output() -> None:
    validator = json_schema_validator(schema=SAMPLE_SCHEMA)
    assert validator(*scripted_outcome(text='{"ok": true}')).status == "pass"


def test_json_schema_fails_on_violation() -> None:
    validator = json_schema_validator(schema=SAMPLE_SCHEMA)
    result = validator(*scripted_outcome(text='{"ok": "yes"}'))
    assert result.status == "fail"
    assert result.reason is not None
    assert "schema" in result.reason


def test_unparseable_json_fails_safe() -> None:
    validator = json_schema_validator(schema=SAMPLE_SCHEMA)
    result = validator(*scripted_outcome(text="this is not json"))
    assert result.status == "fail"
    assert result.reason is not None
    assert "not valid JSON" in result.reason
