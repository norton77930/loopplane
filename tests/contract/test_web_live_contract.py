"""Contract tests for live-session web artifacts."""

from __future__ import annotations

from loopplane.webapi.contract_types import live_contract_artifacts


def test_live_contract_declares_ticket_and_envelopes() -> None:
    artifacts = live_contract_artifacts()

    assert artifacts["version"] == "075-web-capability-management"
    assert artifacts["ticket_fields"] == {
        "ticket",
        "principal_id",
        "session_id",
        "expires_at",
        "issued_at",
        "capabilities",
    }
    assert artifacts["client_message_types"] == {
        "submit",
        "abort",
        "approval_decision",
        "question_answer",
        "ack",
    }
    assert artifacts["server_message_types"] == {"ready", "event", "notice", "error"}


def test_live_contract_keeps_long_lived_credentials_out_of_channel() -> None:
    artifacts = live_contract_artifacts()

    assert "authorization" not in artifacts["ticket_fields"]
    assert "bearer_token" not in artifacts["ticket_fields"]
    assert artifacts["credential_policy"] == "short_lived_ticket"
