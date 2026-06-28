"""Contract tests for 074 web session-management parity artifacts."""

from __future__ import annotations

from loopplane.webapi.contract_types import session_management_contract_artifacts


def test_session_summary_additive_fields_are_declared() -> None:
    artifacts = session_management_contract_artifacts()

    assert artifacts["summary_optional_fields"] == {
        "model",
        "starred",
        "forked_from_session_id",
        "forked_from_sequence",
        "search_snippet",
    }
    assert artifacts["owner_scoped"] is True


def test_session_management_actions_are_declared() -> None:
    artifacts = session_management_contract_artifacts()

    assert artifacts["actions"] == {
        "draft_commit",
        "preferred_model",
        "star",
        "unstar",
        "fork",
        "search",
        "bulk_delete",
    }
    assert artifacts["bulk_delete_requires_confirmation"] is True
