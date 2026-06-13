"""Unit tests for skill loading, merge precedence, variable substitution,
and execution-profile enforcement (T040; FR-050–FR-055).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopplane.approval import HumanApproval, PermissionRule, PolicyAllow, PolicyDeny
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.model import ToolCallRequest, ToolDescriptor
from loopplane.skills import (
    ExecutionProfile,
    Skill,
    SkillAdvertiser,
    load_skills,
    skill_profiles,
    substitute,
)

pytestmark = pytest.mark.anyio


def _write_skill(directory: Path, name: str, **overrides: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "name": name,
        "description": f"the {name} skill",
        "instructions": f"do the {name} thing",
    }
    payload.update(overrides)
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


# --- loading and validation (FR-051) ---------------------------------------------


def test_valid_skills_load_with_their_profiles(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "review",
        profile={"autonomous_invocation": "forbidden", "approval_required": True},
    )

    loaded, problems = load_skills([tmp_path])

    assert problems == []
    skill = loaded["review"].skill
    assert skill.profile.autonomous_invocation == "forbidden"
    assert skill.profile.approval_required is True


def test_malformed_and_oversize_skills_are_skipped_with_problems(
    tmp_path: Path,
) -> None:
    _write_skill(tmp_path, "good")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    _write_skill(tmp_path, "huge", instructions="x" * 100_000)

    loaded, problems = load_skills([tmp_path], size_cap_bytes=10_000)

    assert set(loaded) == {"good"}
    assert len(problems) == 2


# --- merge precedence (FR-052) -----------------------------------------------------


def test_more_specific_source_wins_on_name_conflicts(tmp_path: Path) -> None:
    broad = tmp_path / "user-level"
    specific = tmp_path / "project-level"
    _write_skill(broad, "deploy", instructions="broad instructions")
    _write_skill(broad, "only-broad")
    _write_skill(specific, "deploy", instructions="specific instructions")

    loaded, problems = load_skills([broad, specific])

    assert problems == []
    assert set(loaded) == {"deploy", "only-broad"}
    assert loaded["deploy"].skill.instructions == "specific instructions"
    assert loaded["deploy"].source.endswith("project-level")


# --- variable substitution (FR-054) -------------------------------------------------


def test_closed_list_variables_substitute() -> None:
    text = "session=${session_id} scope=${working_scope} args=${arguments}"
    substituted = substitute(
        text,
        {"session_id": "s1", "working_scope": "/work", "arguments": "fast"},
    )
    assert substituted == "session=s1 scope=/work args=fast"


def test_variables_outside_the_closed_list_pass_through_literally() -> None:
    text = "${session_id} and ${secret_env} and ${HOME}"
    substituted = substitute(text, {"session_id": "s1", "secret_env": "nope"})
    assert substituted == "s1 and ${secret_env} and ${HOME}"


def test_closed_list_variables_without_a_value_pass_through() -> None:
    assert substitute("args=${arguments}", {}) == "args=${arguments}"


# --- incremental advertisement (FR-053) ----------------------------------------------


def _skill(name: str, description: str = "") -> Skill:
    return Skill(
        name=name,
        description=description or f"the {name} skill",
        instructions=f"instructions for {name}",
    )


def test_advertiser_is_incremental_and_budget_bounded() -> None:
    advertiser = SkillAdvertiser(
        [_skill("alpha"), _skill("beta"), _skill("gamma")],
        prompt_budget_chars=100,
    )

    first = advertiser.augment_for("anything")
    assert first is not None
    assert "alpha" in first and "beta" in first
    assert "gamma" not in first  # over this turn's budget

    second = advertiser.augment_for("anything")
    assert second is not None
    assert "gamma" in second
    assert "alpha" not in second  # already advertised, never repeated

    assert advertiser.augment_for("anything") is None  # nothing new remains


def test_re_establishment_repeats_advertised_skills_without_consuming_budget() -> None:
    advertiser = SkillAdvertiser(
        [_skill("alpha"), _skill("beta")], prompt_budget_chars=1000
    )
    advertiser.augment_for("anything")

    re_established = advertiser.re_establish()

    assert re_established is not None
    assert "alpha" in re_established and "beta" in re_established
    # Re-establishment does not mark anything newly available.
    assert advertiser.augment_for("anything") is None


# --- execution-profile enforcement (FR-055; research A1) -----------------------


def _call(tool_name: str) -> ToolCallRequest:
    return ToolCallRequest(call_id="c1", tool_name=tool_name, input={})


def _descriptor(tool_name: str) -> ToolDescriptor:
    return ToolDescriptor(
        name=tool_name, description="d", input_schema={"type": "object"}
    )


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def _emitter() -> EventEmitter:
    return EventEmitter(session_id="s1", sequencer=EventSequencer(), sink=_Collector())


async def test_forbidden_autonomous_invocation_is_refused_outright(
    tmp_path: Path,
) -> None:
    profiles = {"skill:locked": ExecutionProfile(autonomous_invocation="forbidden")}
    # Even a persistent allow rule cannot override the capability gate.
    approval = HumanApproval(
        rules=[PermissionRule(matcher="skill:locked", effect="allow", scope="project")],
        skill_profiles=profiles,
    )

    verdict = await approval(
        _call("skill:locked"),
        _descriptor("skill:locked"),
        RunContext(session_id="s1", working_scope=tmp_path),
        _emitter(),
    )

    assert isinstance(verdict, PolicyDeny)
    assert "autonomous" in verdict.reason


async def test_approval_required_is_not_satisfied_by_an_allow_rule(
    tmp_path: Path,
) -> None:
    profiles = {"skill:risky": ExecutionProfile(approval_required=True)}
    approval = HumanApproval(
        rules=[PermissionRule(matcher="skill:risky", effect="allow", scope="project")],
        skill_profiles=profiles,
    )

    # No reviewer attached: the forced "ask" resolves as deny.
    verdict = await approval(
        _call("skill:risky"),
        _descriptor("skill:risky"),
        RunContext(session_id="s1", working_scope=tmp_path),
        _emitter(),
    )

    assert isinstance(verdict, PolicyDeny)
    assert "no reviewer available" in verdict.reason


async def test_approval_required_is_satisfied_by_a_session_scoped_human_decision(
    tmp_path: Path,
) -> None:
    profiles = {"skill:risky": ExecutionProfile(approval_required=True)}
    approval = HumanApproval(rules=[], skill_profiles=profiles)
    context = RunContext(
        session_id="s1",
        working_scope=tmp_path,
        session_approval_memory={"skill:risky": "allow"},
    )

    verdict = await approval(
        _call("skill:risky"), _descriptor("skill:risky"), context, _emitter()
    )

    assert verdict == PolicyAllow()


def test_skill_profiles_maps_loaded_skills_to_tool_names(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "locked",
        profile={"autonomous_invocation": "forbidden", "approval_required": False},
    )
    loaded, _ = load_skills([tmp_path])

    profiles = skill_profiles(loaded)

    assert profiles["skill:locked"].autonomous_invocation == "forbidden"
