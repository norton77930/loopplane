"""Unit 041: configurable proactive auto-compaction.

The prompt assembler already runs a proactive pre-send compaction check at the
model's full capacity; this unit makes its threshold configurable via an
additive, default-``None`` ``RuntimeConfig.auto_compact_threshold``. ``None`` ==
today's full-capacity behavior (byte-identical); a fraction ``f`` in ``(0, 1]``
compacts proactively at ``f * capacity``. ``compact_history`` and the size
heuristic are reused unchanged; the reactive overflow backstop is untouched;
compaction emits no event. All offline.
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.host import ConfigError, LoopPlaneHost, RuntimeConfig
from loopplane.loop.assembly import PromptAssembler
from loopplane.model import (
    ModelIncrement,
    ModelRequest,
    ScriptedModel,
    ScriptedOverflow,
    ScriptedTurn,
    SummaryMarkerBlock,
    TextBlock,
    TextIncrement,
)

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def __call__(self, event: object) -> None:
        if getattr(event, "type", None) == "run-terminated":
            self.reasons.append(event.payload.reason)  # type: ignore[attr-defined]


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


def _request_has_summary(request: ModelRequest) -> bool:
    return any(
        isinstance(block, SummaryMarkerBlock)
        for message in request.context
        for block in message.blocks
    )


# --- _effective_capacity computation (Contract C4) ---------------------------


def test_effective_capacity_none_is_full_capacity() -> None:
    assembler = PromptAssembler(compact_threshold=None)
    assert assembler._effective_capacity(1000) == 1000


def test_effective_capacity_one_is_full_capacity() -> None:
    assembler = PromptAssembler(compact_threshold=1.0)
    assert assembler._effective_capacity(1000) == 1000


def test_effective_capacity_fraction_scales_capacity() -> None:
    assembler = PromptAssembler(compact_threshold=0.5)
    assert assembler._effective_capacity(1000) == 500
    assembler = PromptAssembler(compact_threshold=0.8)
    assert assembler._effective_capacity(1000) == 800


# --- proactive compaction at a configured threshold (Contracts C1, C2) -------


async def _drive_growing_history(
    *,
    auto_compact_threshold: float | None,
    context_capacity: int,
    tmp_path: Path,
    warmups: int,
) -> RecordingModel:
    """Drive `warmups` text-only turns then one more, returning the recording
    model so the assembled requests can be inspected."""
    script = [
        ScriptedTurn(increments=[TextIncrement(text="a sufficiently long answer " * 6)])
        for _ in range(warmups + 1)
    ]
    model = RecordingModel(
        ScriptedModel(script=script, context_capacity=context_capacity)
    )
    controller = RuntimeController(
        model=model,
        gateway=ToolGateway(),
        event_sink=_Collector(),
        enable_assembly=True,
        assembly_keep_last=2,
        auto_compact_threshold=auto_compact_threshold,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    for i in range(warmups + 1):
        await controller.drive(session_id, [TextBlock(text=f"prompt number {i} " * 4)])
    return model


async def test_threshold_triggers_proactive_compaction(tmp_path: Path) -> None:
    # A small capacity + a low threshold so a few turns push the estimate over
    # threshold * capacity well before the full capacity.
    model = await _drive_growing_history(
        auto_compact_threshold=0.5,
        context_capacity=200,
        tmp_path=tmp_path,
        warmups=4,
    )
    # The model never overflowed (scripted turns, no ScriptedOverflow), and by the
    # final turn the proactive check compacted the history before the model call.
    assert _request_has_summary(model.requests[-1])


async def test_threshold_changes_outcome_for_same_history_and_capacity() -> None:
    """The strongest, heuristic-robust proof: the SAME history and SAME capacity
    compacts with a fraction threshold but not with None — isolating the trigger
    from any growth dynamics."""
    from loopplane.loop import SessionHistory

    async def _build(history: SessionHistory) -> None:
        # ~600 chars of text → ~150 estimated tokens (chars/4).
        await history.append("user", [TextBlock(text="x" * 300)])
        await history.append("assistant", [TextBlock(text="y" * 300)])

    capacity = 500  # estimate (~150) < 500, so None never triggers...

    off_history = SessionHistory()
    await _build(off_history)
    off = PromptAssembler(compact_threshold=None)
    off.assemble(history=off_history, tools=[], capacity=capacity, prompt="go")
    assert not any(
        isinstance(block, SummaryMarkerBlock)
        for entry in off_history.snapshot()
        for block in entry.blocks
    )

    on_history = SessionHistory()
    await _build(on_history)
    # ...but 0.2 * 500 = 100 < ~150, so the threshold DOES trigger.
    on = PromptAssembler(compact_threshold=0.2)
    on.assemble(history=on_history, tools=[], capacity=capacity, prompt="go")
    assert any(
        isinstance(block, SummaryMarkerBlock)
        for entry in on_history.snapshot()
        for block in entry.blocks
    )


async def test_below_threshold_does_not_compact(tmp_path: Path) -> None:
    # A large capacity so a single short turn stays well under threshold*capacity.
    model = await _drive_growing_history(
        auto_compact_threshold=0.8,
        context_capacity=100_000,
        tmp_path=tmp_path,
        warmups=0,
    )
    assert not _request_has_summary(model.requests[-1])


# --- default None == today's behavior (Contract C3) --------------------------


async def test_default_none_does_not_compact_below_full_capacity(
    tmp_path: Path,
) -> None:
    # With no threshold and a large capacity, the same growth that triggered at
    # 0.5 above must NOT compact (identical to today: only the full capacity
    # triggers).
    model = await _drive_growing_history(
        auto_compact_threshold=None,
        context_capacity=100_000,
        tmp_path=tmp_path,
        warmups=4,
    )
    assert not _request_has_summary(model.requests[-1])


async def test_default_none_still_compacts_above_full_capacity(
    tmp_path: Path,
) -> None:
    # With no threshold but a tiny full capacity, the EXISTING full-capacity
    # proactive check still fires (the pre-threshold behavior is preserved).
    model = await _drive_growing_history(
        auto_compact_threshold=None,
        context_capacity=50,
        tmp_path=tmp_path,
        warmups=4,
    )
    assert _request_has_summary(model.requests[-1])


# --- reactive ContextOverflowError backstop unchanged (Contract C5) ----------


async def test_reactive_backstop_unchanged_with_threshold(tmp_path: Path) -> None:
    sink = _Collector()
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="warm up one " * 5)]),
            ScriptedTurn(increments=[TextIncrement(text="warm up two " * 5)]),
            ScriptedOverflow(),
            ScriptedTurn(increments=[TextIncrement(text="fits after compaction")]),
        ],
        context_capacity=100_000,
    )
    controller = RuntimeController(
        model=model,
        gateway=ToolGateway(),
        event_sink=sink,
        enable_assembly=True,
        assembly_keep_last=2,
        auto_compact_threshold=0.8,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="warm up one")])
    await controller.drive(session_id, [TextBlock(text="warm up two")])
    await controller.drive(session_id, [TextBlock(text="now overflow")])
    assert sink.reasons[-1] == "natural-completion"


async def test_second_overflow_surfaces_failure_with_threshold(
    tmp_path: Path,
) -> None:
    sink = _Collector()
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="history fodder " * 5)]),
            ScriptedTurn(increments=[TextIncrement(text="more fodder " * 5)]),
            ScriptedOverflow(),
            ScriptedOverflow(),
        ],
        context_capacity=100_000,
    )
    controller = RuntimeController(
        model=model,
        gateway=ToolGateway(),
        event_sink=sink,
        enable_assembly=True,
        assembly_keep_last=2,
        auto_compact_threshold=0.8,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="warm up one")])
    await controller.drive(session_id, [TextBlock(text="warm up two")])
    await controller.drive(session_id, [TextBlock(text="overflow twice")])
    assert sink.reasons[-1] == "unrecoverable-error"


# --- config wiring: round-trip, validation, no-secret (Contracts C7, C8) -----


def _model() -> ScriptedModel:
    return ScriptedModel(script=[], context_capacity=1_000)


def test_threshold_round_trips_from_mapping_and_defaults_none() -> None:
    config = RuntimeConfig.from_mapping(
        {"model": _model(), "auto_compact_threshold": 0.75}
    )
    assert config.auto_compact_threshold == 0.75
    default = RuntimeConfig.from_mapping({"model": _model()})
    assert default.auto_compact_threshold is None


def test_threshold_one_is_valid() -> None:
    # 1.0 == the full-capacity trigger; valid.
    LoopPlaneHost(RuntimeConfig(model=_model(), auto_compact_threshold=1.0))


@pytest.mark.parametrize("bad", [0.0, -0.5, 1.5, 2.0, float("nan"), float("inf")])
def test_invalid_threshold_is_rejected_fast(bad: float) -> None:
    with pytest.raises(ConfigError):
        LoopPlaneHost(RuntimeConfig(model=_model(), auto_compact_threshold=bad))


def test_auto_compact_threshold_is_not_a_secret_field() -> None:
    names = {f.name for f in dataclasses.fields(RuntimeConfig)}
    assert "auto_compact_threshold" in names
    secrets = {"api_key", "token", "secret", "password", "credential"}
    assert not (names & secrets)
