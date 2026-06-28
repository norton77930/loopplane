"""Backend-owned web contract artifact helpers for 074.

This module is intentionally small at setup time. Implementation tasks extend it
with deterministic fixtures used by contract/type drift tests.
"""

from __future__ import annotations

from typing import cast

WEB_CONTRACT_VERSION = "074-web-parity-foundation"


def live_contract_artifacts() -> dict[str, object]:
    """Return deterministic live-channel metadata for tests and drift checks."""

    return {
        "version": WEB_CONTRACT_VERSION,
        "credential_policy": "short_lived_ticket",
        "ticket_fields": {
            "ticket",
            "principal_id",
            "session_id",
            "expires_at",
            "issued_at",
            "capabilities",
        },
        "client_message_types": {
            "submit",
            "abort",
            "approval_decision",
            "question_answer",
            "ack",
        },
        "server_message_types": {"ready", "event", "notice", "error"},
    }


def session_management_contract_artifacts() -> dict[str, object]:
    """Return additive session-management contract metadata."""

    return {
        "version": WEB_CONTRACT_VERSION,
        "owner_scoped": True,
        "summary_optional_fields": {
            "model",
            "starred",
            "forked_from_session_id",
            "forked_from_sequence",
            "search_snippet",
        },
        "actions": {
            "draft_commit",
            "preferred_model",
            "star",
            "unstar",
            "fork",
            "search",
            "bulk_delete",
        },
        "bulk_delete_requires_confirmation": True,
    }


def contract_type_artifacts() -> dict[str, object]:
    """Return backend-owned web type artifact metadata."""

    session_fields = {
        "session_id",
        "label",
        "created_at",
        "last_active_at",
        "model",
        "starred",
        "forked_from_session_id",
        "forked_from_sequence",
        "search_snippet",
    }
    event_types = {
        "assistant-output-increment",
        "assistant-reasoning-increment",
        "tool-call-started",
        "tool-call-completed",
        "approval-requested",
        "question-asked",
        "turn-completed",
        "run-terminated",
    }
    return {
        "version": WEB_CONTRACT_VERSION,
        "session_summary_fields": session_fields,
        "event_types": event_types,
        "live": live_contract_artifacts(),
        "session_management": session_management_contract_artifacts(),
    }


def validate_contract_artifact(artifact: dict[str, object]) -> None:
    """Fail clearly when a required web-facing field or event type drifts."""

    required_session_fields = cast(
        set[str], contract_type_artifacts()["session_summary_fields"]
    )
    required_event_types = cast(set[str], contract_type_artifacts()["event_types"])
    actual_session_fields = artifact.get("session_summary_fields")
    actual_event_types = artifact.get("event_types")
    if not isinstance(actual_session_fields, set):
        raise ValueError("session_summary_fields must be a set")
    if not isinstance(actual_event_types, set):
        raise ValueError("event_types must be a set")
    missing_session = required_session_fields - actual_session_fields
    if missing_session:
        missing = ", ".join(sorted(missing_session))
        raise ValueError(f"missing session fields: {missing}")
    missing_events = required_event_types - actual_event_types
    if missing_events:
        raise ValueError(f"missing event types: {', '.join(sorted(missing_events))}")
