"""US4 acceptance 4.1–4.4 plus compaction edge cases (FR-008, FR-050–FR-055,
FR-070–FR-074): assembly-time augmentation with pristine durable history,
incremental advertisement, profile enforcement, and compaction that never
splits a call from its result, retries exactly once on overflow, and
re-establishes needed augmentations.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.approval import HumanApproval
from loopplane.checkpoint import FileCheckpointStore, UserInputRecord
from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.loop import SessionHistory, compact_history
from loopplane.memory import MemoryEntry, MemoryStore
from loopplane.model import (
    ModelIncrement,
    ModelRequest,
    ScriptedModel,
    ScriptedOverflow,
    ScriptedTurn,
    SummaryMarkerBlock,
    TextBlock,
    TextIncrement,
    ToolCallBlock,
    ToolCallRequest,
    ToolResultBlock,
)
from loopplane.skills import SkillToolAdapter, load_skills, skill_profiles

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


class RecordingModel:
    """Wraps the scripted substitute and records every assembled request."""

    def __init__(self, inner: ScriptedModel) -> None:
        self._inner = inner
        self.requests: list[ModelRequest] = []

    def context_capacity(self) -> int:
        return self._inner.context_capacity()

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.requests.append(request)
        async for increment in self._inner.stream_turn(request):
            yield increment


def _write_skill(directory: Path, name: str, **overrides: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "name": name,
        "description": f"the {name} skill",
        "instructions": f"do the {name} thing",
    }
    payload.update(overrides)
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _augmentation_text(request: ModelRequest) -> str:
    first = request.context[0]
    if first.role != "user":
        return ""
    return "".join(block.text for block in first.blocks if isinstance(block, TextBlock))


async def test_memory_injection_keeps_durable_history_verbatim(tmp_path: Path) -> None:
    """Acceptance 4.1: selected entries reach the assembled context only."""
    memory = MemoryStore(tmp_path / "memory")
    memory.write(
        MemoryEntry(
            type="project",
            name="deploy-notes",
            description="how to deploy the service safely",
            body="always run the smoke test first",
        )
    )
    model = RecordingModel(
        ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="ok")])],
            context_capacity=100_000,
        )
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    sink = EventCollector()
    checkpoint = FileCheckpointStore(tmp_path / "sessions")
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=sink,
        checkpoint_store=checkpoint,
        memory_store=memory,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="how do I deploy this?")])

    augmentation = _augmentation_text(model.requests[0])
    assert "always run the smoke test first" in augmentation

    # Durable history records the prompt verbatim, with no injected content.
    history = controller.history_snapshot(session_id)
    assert history[0].blocks == (TextBlock(text="how do I deploy this?"),)
    records, _ = checkpoint.load(session_id)
    user_records = [r for r in records if isinstance(r, UserInputRecord)]
    assert user_records[0].payload.blocks == [TextBlock(text="how do I deploy this?")]
    assert all(
        "smoke test" not in json.dumps(record.payload.model_dump(mode="json"))
        for record in user_records
    )


async def test_skills_advertise_incrementally_within_the_budget(tmp_path: Path) -> None:
    """Acceptance 4.2: each skill is advertised once; the advertisement
    stays within its prompt budget.
    """
    skills_dir = tmp_path / "skills"
    for name in ("alpha", "beta", "gamma"):
        _write_skill(skills_dir, name)
    loaded, problems = load_skills([skills_dir])
    assert problems == []

    model = RecordingModel(
        ScriptedModel(
            script=[
                ScriptedTurn(increments=[TextIncrement(text="one")]),
                ScriptedTurn(increments=[TextIncrement(text="two")]),
                ScriptedTurn(increments=[TextIncrement(text="three")]),
            ],
            context_capacity=100_000,
        )
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=EventCollector(),
        skills=loaded,
        skill_prompt_budget_chars=100,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="turn one")])
    await controller.drive(session_id, [TextBlock(text="turn two")])
    await controller.drive(session_id, [TextBlock(text="turn three")])

    first, second, third = (_augmentation_text(request) for request in model.requests)
    assert "skill:alpha" in first and "skill:beta" in first
    assert "skill:gamma" not in first  # beyond this turn's budget
    assert len(first) <= 200

    assert "skill:gamma" in second
    assert "skill:alpha" not in second  # advertised once, not repeated

    assert "skill:" not in third  # nothing newly available


async def test_forbidden_skill_is_refused_for_autonomous_use(tmp_path: Path) -> None:
    """Acceptance 4.3: the capability gate refuses the invocation and the
    run continues.
    """
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "locked",
        profile={"autonomous_invocation": "forbidden"},
    )
    loaded, _ = load_skills([skills_dir])

    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    ToolCallRequest(call_id="c1", tool_name="skill:locked", input={})
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="moving on")]),
        ],
        context_capacity=100_000,
    )
    gateway = ToolGateway(
        decide=HumanApproval(rules=[], skill_profiles=skill_profiles(loaded))
    )
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    gateway.register_adapter(SkillToolAdapter(loaded))
    sink = EventCollector()
    controller = RuntimeController(model=model, gateway=gateway, event_sink=sink)
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="use the locked skill")])

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"
    assert completed.payload.error is not None
    assert completed.payload.error.category == "policy-denial"
    assert "autonomous" in completed.payload.error.reason
    assert sink.events[-1].payload.reason == "natural-completion"


async def test_allowed_skill_invocation_returns_substituted_instructions(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "greet",
        instructions="greet within ${working_scope} using ${arguments}",
    )
    loaded, _ = load_skills([skills_dir])

    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    ToolCallRequest(
                        call_id="c1",
                        tool_name="skill:greet",
                        input={"arguments": "a warm tone"},
                    )
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="done")]),
        ],
        context_capacity=100_000,
    )
    gateway = ToolGateway()
    gateway.register_adapter(SkillToolAdapter(loaded))
    sink = EventCollector()
    controller = RuntimeController(model=model, gateway=gateway, event_sink=sink)
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="greet me")])

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "success"
    text = "".join(
        block.text
        for block in completed.payload.outputs
        if isinstance(block, TextBlock)
    )
    assert "a warm tone" in text
    assert str(tmp_path) in text


async def test_malformed_definitions_skip_and_the_run_proceeds(tmp_path: Path) -> None:
    """Acceptance 4.4: each malformed definition is skipped with a problem
    report; the valid remainder works.
    """
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "good")
    (skills_dir / "broken.json").write_text("{not json", encoding="utf-8")
    loaded, skill_problems = load_skills([skills_dir])
    assert set(loaded) == {"good"}
    assert len(skill_problems) == 1

    memory = MemoryStore(tmp_path / "memory")
    memory.write(
        MemoryEntry(type="user", name="ok", description="a valid entry", body="fine")
    )
    (tmp_path / "memory" / "junk.json").write_text("][", encoding="utf-8")
    entries, memory_problems = memory.scan()
    assert [e.name for e in entries] == ["ok"]
    assert len(memory_problems) == 1

    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="still fine")])],
        context_capacity=100_000,
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    sink = EventCollector()
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=sink,
        memory_store=memory,
        skills=loaded,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="a valid entry please")])

    assert sink.events[-1].payload.reason == "natural-completion"


# --- compaction edge cases (FR-008, FR-053) -----------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


async def test_compaction_never_splits_a_call_from_its_result() -> None:
    history = SessionHistory()
    await history.append("user", [TextBlock(text="start task one")])
    await history.append("assistant", [TextBlock(text="thinking about it at length")])
    await history.append("user", [TextBlock(text="now use the tool")])
    await history.append(
        "assistant",
        [ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"})],
    )
    await history.append(
        "user",
        [
            ToolResultBlock(
                call_id="c1", outcome="success", outputs=[TextBlock(text="x")]
            )
        ],
    )
    await history.append("assistant", [TextBlock(text="all wrapped up")])

    compacted = compact_history(history, keep_last=2)

    assert compacted is True
    entries = history.snapshot()
    assert isinstance(entries[0].blocks[0], SummaryMarkerBlock)

    # Every call in the retained span still has its result in the span.
    retained_calls = {
        block.call_id
        for entry in entries
        for block in entry.blocks
        if isinstance(block, ToolCallBlock)
    }
    retained_results = {
        block.call_id
        for entry in entries
        for block in entry.blocks
        if isinstance(block, ToolResultBlock)
    }
    assert retained_calls <= retained_results


async def test_overflow_compacts_and_retries_exactly_once(tmp_path: Path) -> None:
    model = RecordingModel(
        ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[TextIncrement(text="a fairly long answer " * 5)]
                ),
                ScriptedTurn(
                    increments=[TextIncrement(text="another long answer " * 5)]
                ),
                ScriptedOverflow(),
                ScriptedTurn(increments=[TextIncrement(text="fits after compaction")]),
            ],
            context_capacity=100_000,
        )
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    sink = EventCollector()
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=sink,
        enable_assembly=True,
        assembly_keep_last=2,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="warm up one")])
    await controller.drive(session_id, [TextBlock(text="warm up two")])
    await controller.drive(session_id, [TextBlock(text="now overflow")])

    assert sink.events[-1].payload.reason == "natural-completion"
    entries = controller.history_snapshot(session_id)
    assert any(
        isinstance(block, SummaryMarkerBlock)
        for entry in entries
        for block in entry.blocks
    )


async def test_a_second_overflow_surfaces_the_failure(tmp_path: Path) -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="long history fodder " * 5)]),
            ScriptedTurn(increments=[TextIncrement(text="more history fodder " * 5)]),
            ScriptedOverflow(),
            ScriptedOverflow(),
        ],
        context_capacity=100_000,
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    sink = EventCollector()
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=sink,
        enable_assembly=True,
        assembly_keep_last=2,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="warm up one")])
    await controller.drive(session_id, [TextBlock(text="warm up two")])
    await controller.drive(session_id, [TextBlock(text="overflow twice")])

    assert sink.events[-1].payload.reason == "unrecoverable-error"


async def test_post_compaction_reestablishment_of_advertised_skills(
    tmp_path: Path,
) -> None:
    """FR-053: advertised skills are re-established after compaction without
    being treated as newly available.
    """
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "alpha")
    loaded, _ = load_skills([skills_dir])

    model = RecordingModel(
        ScriptedModel(
            script=[
                ScriptedTurn(increments=[TextIncrement(text="long answer one " * 8)]),
                ScriptedTurn(increments=[TextIncrement(text="long answer two " * 8)]),
                ScriptedOverflow(),
                ScriptedTurn(increments=[TextIncrement(text="after compaction")]),
            ],
            context_capacity=100_000,
        )
    )
    gateway = ToolGateway()
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=EventCollector(),
        skills=loaded,
        assembly_keep_last=2,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="one")])
    await controller.drive(session_id, [TextBlock(text="two")])
    await controller.drive(session_id, [TextBlock(text="three")])

    # Turn 1 advertised alpha; turn 2 had nothing new; the post-overflow
    # retry re-establishes it.
    first = _augmentation_text(model.requests[0])
    assert "skill:alpha" in first
    second = _augmentation_text(model.requests[1])
    assert "skill:alpha" not in second
    retry = _augmentation_text(model.requests[-1])
    assert "skill:alpha" in retry
