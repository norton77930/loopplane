"""US1 Web agent-controls contract tests (spec 077 T008/T012)."""

from __future__ import annotations

from loopplane.webapi.contract_types import agent_controls_contract_artifacts
from loopplane.webapi.models import AgentControlProjectionView, RunRequest


def test_agent_controls_contract_is_owner_scoped_and_public_safe() -> None:
    contract = agent_controls_contract_artifacts()

    assert contract["route"] == "GET /v1/sessions/{session_id}/agent-controls"
    assert contract["owner_scoped"] is True
    assert contract["selection_scope"] == "run"
    assert "bypassPermissions" not in contract["browser_selectable_modes"]
    assert contract["rejected_input_echo"] is False
    assert not (
        set(contract["forbidden_response_fields"])
        & set(AgentControlProjectionView.model_fields)
    )


def test_run_input_has_only_an_optional_permission_mode_extension() -> None:
    assert RunRequest.model_fields["permission_mode"].default is None
    assert RunRequest(prompt="hello").permission_mode is None
    assert RunRequest(prompt="hello", permission_mode="plan").permission_mode == "plan"
