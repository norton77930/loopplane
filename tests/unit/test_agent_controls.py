"""US1 safe agent-control projection tests (spec 077 T005/T009)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import anyio
import pytest

from loopplane.events import QuestionAskedEvent, RuntimeEvent
from loopplane.governance import PermissionRuleSet, PermissionRuleSpec
from loopplane.host import LoopPlaneHost, RuntimeConfig, Session, StorageConfig
from loopplane.host.agent_controls import build_agent_control_projection
from loopplane.model import (
    ModelIncrement,
    ModelRequest,
    ScriptedModel,
    ScriptedTurn,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
    TurnEnd,
)
from loopplane.pricing import PricingRate, PricingTable
from loopplane.tools import InternalToolAdapter

pytestmark = pytest.mark.anyio


def _config(**changes: object) -> RuntimeConfig:
    return RuntimeConfig(
        model=ScriptedModel(script=[], context_capacity=1_000), **changes
    )


class _PlanExitGateModel:
    def __init__(self) -> None:
        self.calls = 0
        self.second_turn_started = anyio.Event()
        self.release = anyio.Event()

    def context_capacity(self) -> int:
        return 1_000

    async def stream_turn(
        self, _request: ModelRequest
    ) -> AsyncIterator[ModelIncrement]:
        self.calls += 1
        if self.calls == 1:
            yield ToolCallRequest(
                call_id="exit-1",
                tool_name="exit_plan_mode",
                input={"plan": "approved plan"},
            )
            yield TurnEnd(stop_reason="tool_use", usage=TokenUsage())
            return
        self.second_turn_started.set()
        await self.release.wait()
        yield TextIncrement(text="done")
        yield TurnEnd(stop_reason="end_turn", usage=TokenUsage())


def test_projection_is_safe_read_only_when_no_browser_modes_are_configured() -> None:
    projection = build_agent_control_projection(_config(), session_id="session-1")

    assert projection.session_id == "session-1"
    assert projection.permission.selectable_modes == ()
    assert projection.actions == ()
    assert projection.permission.selection_scope == "run"
    assert projection.budget.tracking == "unknown"


def test_projection_fails_closed_for_duplicate_or_bypass_modes() -> None:
    duplicate = build_agent_control_projection(
        _config(browser_permission_modes=("plan", "plan")), session_id="session-1"
    )
    bypass = build_agent_control_projection(
        _config(browser_permission_modes=("acceptEdits", "bypassPermissions")),
        session_id="session-1",
    )

    assert duplicate.permission.selectable_modes == ()
    assert duplicate.actions == ()
    assert bypass.permission.selectable_modes == ()
    assert bypass.actions == ()


def test_projection_includes_read_upload_action_only_when_host_advertises_it() -> None:
    available = build_agent_control_projection(
        _config(), session_id="session-1", read_upload_available=True
    )
    unavailable = build_agent_control_projection(
        _config(), session_id="session-1", read_upload_available=False
    )

    assert available.actions == ("attach_non_image_upload",)
    assert unavailable.actions == ()


def test_projection_exposes_only_a_bounded_rule_summary() -> None:
    projection = build_agent_control_projection(
        _config(
            permission_rules=PermissionRuleSet(
                rules=(
                    PermissionRuleSpec(
                        tool="write_file",
                        match={"path": "private/**"},
                        decision="deny",
                    ),
                    PermissionRuleSpec(
                        tool="run_command",
                        match={"command": "^rm"},
                        decision="ask",
                    ),
                ),
                default="allow",
            )
        ),
        session_id="session-1",
    )

    permission = projection.permission
    assert permission.rules_configured is True
    assert permission.rule_default == "allow"
    assert permission.rule_decisions == ("deny", "ask", "allow")
    assert "write_file" not in repr(projection)
    assert "private/**" not in repr(projection)
    assert "^rm" not in repr(projection)


async def test_host_projects_existing_budget_checker_as_enum_only_posture() -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="done")])],
                context_capacity=1_000,
            ),
            pricing_table=PricingTable(
                rates={
                    "model-a": PricingRate(
                        input_rate=Decimal("0.001"),
                        output_rate=Decimal("0.002"),
                    )
                }
            ),
            model_id="model-a",
            per_session_usd=Decimal("1"),
        )
    )

    outcome = await host.run("priced", _discard, principal_id="alice")
    projection = host.agent_controls(outcome.session_id)

    assert projection.budget.tracking == "available"
    assert projection.budget.pricing == "priced"
    assert projection.budget.message_guard == "disabled"
    assert projection.budget.session_guard == "within"
    assert projection.budget.monthly_guard == "disabled"
    assert projection.budget.pre_turn_guard == "disabled"
    assert "model-a" not in repr(projection.budget)
    assert "Decimal" not in repr(projection.budget)
    assert "alice" not in repr(projection.budget)


async def test_host_records_an_accepted_mode_only_as_ephemeral_settled_posture() -> (
    None
):
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[ScriptedTurn(increments=[TextIncrement(text="done")])],
                context_capacity=1_000,
            ),
            browser_permission_modes=("plan",),
        )
    )

    outcome = await host.run(
        "make a plan",
        _discard,
        principal_id="alice",
        permission_mode="plan",
    )
    projection = host.agent_controls(outcome.session_id)

    assert projection.permission.active_run is None
    assert projection.permission.last_accepted_run is not None
    assert projection.permission.last_accepted_run.mode == "plan"
    assert projection.permission.last_accepted_run.state == "settled"
    assert projection.permission.last_accepted_run.plan_active is False


async def test_active_projection_tracks_mutable_plan_state_after_approved_exit() -> (
    None
):
    model = _PlanExitGateModel()
    host = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            tool_adapters=(InternalToolAdapter(),),
            browser_permission_modes=("plan",),
        )
    )
    asked = anyio.Event()
    request_id: list[str] = []

    async def sink(event: RuntimeEvent) -> None:
        if isinstance(event, QuestionAskedEvent):
            request_id.append(event.payload.request_id)
            asked.set()

    async with host.session(sink, principal_id="alice") as session:
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(_submit_plan, session)
            await asked.wait()
            before = host.agent_controls(session.session_id)
            assert before.permission.active_run is not None
            assert before.permission.active_run.plan_active is True

            assert session.answer_question(request_id[0], ["approve"]) is True
            await model.second_turn_started.wait()
            after = host.agent_controls(session.session_id)
            assert after.permission.active_run is not None
            assert after.permission.active_run.plan_active is False
            model.release.set()


async def test_rebuilt_host_does_not_reconstruct_last_posture_from_checkpoint(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    config = RuntimeConfig(
        model=ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="done")])],
            context_capacity=1_000,
        ),
        storage=StorageConfig(root=tmp_path),
        browser_permission_modes=("plan",),
    )
    first = LoopPlaneHost(config)
    outcome = await first.run("plan", _discard, permission_mode="plan")
    assert (
        first.agent_controls(outcome.session_id).permission.last_accepted_run
        is not None
    )

    rebuilt = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(script=[], context_capacity=1_000),
            storage=StorageConfig(root=tmp_path),
            browser_permission_modes=("plan",),
        )
    )

    projection = rebuilt.agent_controls(outcome.session_id)
    assert projection.permission.active_run is None
    assert projection.permission.last_accepted_run is None


async def test_host_rejects_unknown_or_bypass_mode_before_a_run_starts() -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(script=[], context_capacity=1_000),
            browser_permission_modes=("acceptEdits",),
        )
    )

    with pytest.raises(ValueError, match="permission mode unavailable"):
        await host.run("blocked", _discard, permission_mode="bypassPermissions")
    with pytest.raises(ValueError, match="permission mode unavailable"):
        await host.run("blocked", _discard, permission_mode="unknown")


async def _submit_plan(session: Session) -> None:
    await session.submit("make a plan", permission_mode="plan")


async def _discard(_event: object) -> None:
    return None
