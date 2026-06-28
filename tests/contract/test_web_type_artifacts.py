"""Contract tests for deterministic web-facing type artifacts."""

from __future__ import annotations

import pytest

from loopplane.webapi.contract_types import (
    contract_type_artifacts,
    validate_contract_artifact,
)


def test_contract_type_artifacts_are_deterministic_and_public_safe() -> None:
    artifacts = contract_type_artifacts()

    assert artifacts == contract_type_artifacts()
    assert artifacts["version"] == "074-web-parity-foundation"
    assert "sk-" not in repr(artifacts)
    assert "ghp_" not in repr(artifacts)


def test_contract_validation_catches_missing_api_field() -> None:
    artifacts = contract_type_artifacts()
    drifted = {
        **artifacts,
        "session_summary_fields": artifacts["session_summary_fields"] - {"session_id"},
    }

    with pytest.raises(ValueError, match="session_id"):
        validate_contract_artifact(drifted)


def test_contract_validation_catches_missing_event_type() -> None:
    artifacts = contract_type_artifacts()
    drifted = {
        **artifacts,
        "event_types": artifacts["event_types"] - {"run-terminated"},
    }

    with pytest.raises(ValueError, match="run-terminated"):
        validate_contract_artifact(drifted)
