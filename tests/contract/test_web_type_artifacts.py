"""Contract tests for deterministic web-facing type artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.webapi.contract_types import (
    api_response_contract_fixtures,
    contract_type_artifacts,
    session_event_contract_fixtures,
    typescript_type_artifact,
    validate_api_response_fixture,
    validate_contract_artifact,
    validate_session_event_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_api_response_fixture_validation_catches_missing_required_field() -> None:
    fixtures = api_response_contract_fixtures()
    drifted = dict(fixtures["session_summary"])
    drifted.pop("session_id")

    with pytest.raises(ValueError, match="session_summary.*session_id"):
        validate_api_response_fixture("session_summary", drifted)


def test_session_event_fixture_validation_catches_payload_drift() -> None:
    fixtures = session_event_contract_fixtures()
    drifted = {
        **fixtures["run_terminated"],
        "payload": {"reason": "natural-completion"},
    }

    with pytest.raises(ValueError, match="run_terminated.*turns_taken"):
        validate_session_event_fixture("run_terminated", drifted)


def test_generated_types_match_backend_owned_artifact() -> None:
    generated = REPO_ROOT / "apps" / "web" / "src" / "api" / "generated.ts"

    assert generated.read_text(encoding="utf-8") == typescript_type_artifact()
