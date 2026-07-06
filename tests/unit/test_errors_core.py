"""Direct unit tests for the Normalized Error shape (errors.py; FR-025).

The single failure shape that crosses the Tool Gateway boundary: its category
wire values and frozen shape are a cross-boundary contract.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from loopplane.errors import ErrorCategory, NormalizedError


def test_error_category_wire_values_are_stable() -> None:
    assert {member.value for member in ErrorCategory} == {
        "unknown-tool",
        "validation",
        "policy-denial",
        "timeout",
        "execution",
        "adapter-fault",
    }


def test_normalized_error_is_frozen() -> None:
    error = NormalizedError(category=ErrorCategory.TIMEOUT, reason="took too long")
    with pytest.raises(ValidationError):
        error.reason = "changed"  # type: ignore[misc]


def test_normalized_error_round_trips_with_wire_category() -> None:
    error = NormalizedError(category=ErrorCategory.POLICY_DENIAL, reason="denied")
    dumped = error.model_dump(mode="json")
    assert dumped == {"category": "policy-denial", "reason": "denied"}
    assert NormalizedError.model_validate(dumped) == error
