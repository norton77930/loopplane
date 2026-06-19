"""Unit 042: optional cheap-model compaction summarizer.

The deferred half of spec 041. Compaction produces a mechanical
``SummaryMarkerBlock`` (turn count + tool names + excerpts). This unit lets a host
supply an optional summarizer ``ModelBoundary`` via the additive, default-``None``
``RuntimeConfig.compaction_summarizer``: when set, compaction summarizes the
dropped span and stores the model summary in the existing marker's
``SummaryDigest.excerpts`` (keeping ``turn_count`` / ``tool_names`` mechanical);
when ``None`` (default), the mechanical digest is byte-identical to today.

The non-negotiable property is FAIL-SAFE: a summarizer error / timeout / empty
output falls back to the mechanical digest and never breaks a run. All offline
(a ``ScriptedModel`` as the summarizer; no network).
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.host import RuntimeConfig
from loopplane.loop.compaction import compact_history
from loopplane.loop.history import HistoryEntry, SessionHistory
from loopplane.loop.summarizer import summarize_compaction
from loopplane.model import (
    ModelIncrement,
    ModelRequest,
    ScriptedFailure,
    ScriptedModel,
    ScriptedOverflow,
    ScriptedTurn,
    SummaryDigest,
    SummaryMarkerBlock,
    TextBlock,
    TextIncrement,
)

pytestmark = pytest.mark.anyio

_SUMMARY = "MODEL SUMMARY: the user set up task one and the tool ran successfully."


class _Collector:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def __call__(self, event: object) -> None:
        if getattr(event, "type", None) == "run-terminated":
            self.reasons.append(event.payload.reason)  # type: ignore[attr-defined]


class _RecordingSummarizer:
    """Wraps a scripted summarizer and records every request it is handed."""

    def __init__(self, inner: ScriptedModel) -> None:
        self._inner = inner
        self.requests: list[ModelRequest] = []

    def context_capacity(self) -> int:
        return self._inner.context_capacity()

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.requests.append(request)
        async for increment in self._inner.stream_turn(request):
            yield increment


class _SlowSummarizer:
    """A summarizer that never yields in time — exercises the timeout guard."""

    def __init__(self) -> None:
        self.called = False

    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        import anyio

        self.called = True
        await anyio.sleep(3600)  # far beyond any guard deadline
        yield TextIncrement(text="too late")  # pragma: no cover


def _summary_model(text: str = _SUMMARY) -> _RecordingSummarizer:
    return _RecordingSummarizer(
        ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
            context_capacity=100_000,
        )
    )


def _dropped_span() -> tuple[HistoryEntry, ...]:
    now = datetime.now(UTC)
    return (
        HistoryEntry(
            role="user", blocks=(TextBlock(text="set up task one"),), recorded_at=now
        ),
        HistoryEntry(
            role="assistant",
            blocks=(TextBlock(text="working on it at length"),),
            recorded_at=now,
        ),
    )


def _mechanical_marker() -> SummaryMarkerBlock:
    return SummaryMarkerBlock(
        digest=SummaryDigest(
            turn_count=2, tool_names=["echo"], excerpts=["set up task one"]
        )
    )


# --- summarize_compaction: the overlay in isolation --------------------------


async def test_overlay_success_puts_model_summary_into_excerpts() -> None:
    marker = _mechanical_marker()
    out = await summarize_compaction(
        summarizer=_summary_model(),
        dropped=_dropped_span(),
        marker=marker,
    )
    # The model summary replaces the excerpts; turn_count / tool_names mechanical.
    assert out.digest.excerpts == [_SUMMARY]
    assert out.digest.turn_count == marker.digest.turn_count
    assert out.digest.tool_names == marker.digest.tool_names


async def test_overlay_passes_dropped_span_and_no_tools() -> None:
    summarizer = _summary_model()
    dropped = _dropped_span()
    await summarize_compaction(
        summarizer=summarizer, dropped=dropped, marker=_mechanical_marker()
    )
    (request,) = summarizer.requests
    assert request.tools == []
    # The dropped turns' text must appear in the summarize request's context.
    joined = "\n".join(
        block.text
        for message in request.context
        for block in message.blocks
        if isinstance(block, TextBlock)
    )
    assert "set up task one" in joined
    assert "working on it at length" in joined


async def test_overlay_raising_summarizer_returns_mechanical_marker() -> None:
    marker = _mechanical_marker()
    summarizer = ScriptedModel(
        script=[ScriptedFailure(error=RuntimeError("boom"))], context_capacity=100_000
    )
    out = await summarize_compaction(
        summarizer=summarizer, dropped=_dropped_span(), marker=marker
    )
    assert out == marker  # unchanged mechanical digest


async def test_overlay_overflow_summarizer_returns_mechanical_marker() -> None:
    marker = _mechanical_marker()
    summarizer = ScriptedModel(script=[ScriptedOverflow()], context_capacity=100_000)
    out = await summarize_compaction(
        summarizer=summarizer, dropped=_dropped_span(), marker=marker
    )
    assert out == marker


async def test_overlay_empty_output_returns_mechanical_marker() -> None:
    marker = _mechanical_marker()
    summarizer = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="   ")])],
        context_capacity=100_000,
    )
    out = await summarize_compaction(
        summarizer=summarizer, dropped=_dropped_span(), marker=marker
    )
    assert out == marker


async def test_overlay_timeout_returns_mechanical_marker() -> None:
    marker = _mechanical_marker()
    slow = _SlowSummarizer()
    out = await summarize_compaction(
        summarizer=slow, dropped=_dropped_span(), marker=marker, timeout_seconds=0.05
    )
    assert slow.called
    assert out == marker


# --- driven through the controller (reactive compaction) ---------------------


async def _drive_to_reactive_compaction(
    *, summarizer: object | None, tmp_path: Path
) -> tuple[_Collector, SessionHistory, RuntimeController]:
    """Two warm-up turns, then a forced overflow → reactive compaction + retry."""
    sink = _Collector()
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="warm up one " * 4)]),
            ScriptedTurn(increments=[TextIncrement(text="warm up two " * 4)]),
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
        compaction_summarizer=summarizer,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="warm up one")])
    await controller.drive(session_id, [TextBlock(text="warm up two")])
    await controller.drive(session_id, [TextBlock(text="now overflow")])
    history = controller._require(session_id).history
    return sink, history, controller


def _marker_excerpts(history: SessionHistory) -> list[str]:
    for entry in history.snapshot():
        for block in entry.blocks:
            if isinstance(block, SummaryMarkerBlock):
                return block.digest.excerpts
    return []


async def test_reactive_compaction_uses_model_summary(tmp_path: Path) -> None:
    summarizer = _summary_model()
    sink, history, _ = await _drive_to_reactive_compaction(
        summarizer=summarizer, tmp_path=tmp_path
    )
    assert sink.reasons[-1] == "natural-completion"  # the run completed
    assert _marker_excerpts(history) == [_SUMMARY]  # the model summary landed
    assert summarizer.requests  # the summarizer was consulted


async def test_default_none_is_mechanical_and_no_model_call(tmp_path: Path) -> None:
    sink, history, _ = await _drive_to_reactive_compaction(
        summarizer=None, tmp_path=tmp_path
    )
    assert sink.reasons[-1] == "natural-completion"
    excerpts = _marker_excerpts(history)
    assert excerpts and excerpts != [_SUMMARY]  # the mechanical excerpts, not a summary


async def test_default_none_marker_is_byte_identical_to_pre_042(tmp_path: Path) -> None:
    """The strongest off-path proof: with no summarizer, the marker the controller
    produces equals the one the bare mechanical `compact_history` produces over the
    same dropped span."""
    _, history, _ = await _drive_to_reactive_compaction(
        summarizer=None, tmp_path=tmp_path
    )
    snapshot = history.snapshot()
    marker_block = snapshot[0].blocks[0]
    assert isinstance(marker_block, SummaryMarkerBlock)

    # Reconstruct the dropped span and run the mechanical compaction directly.
    reference = SessionHistory()
    reference.restore(
        [
            HistoryEntry(
                role="user",
                blocks=(TextBlock(text="warm up one"),),
                recorded_at=datetime.now(UTC),
            ),
            HistoryEntry(
                role="assistant",
                blocks=(TextBlock(text="warm up one " * 4),),
                recorded_at=datetime.now(UTC),
            ),
            HistoryEntry(
                role="user",
                blocks=(TextBlock(text="warm up two"),),
                recorded_at=datetime.now(UTC),
            ),
            HistoryEntry(
                role="assistant",
                blocks=(TextBlock(text="warm up two " * 4),),
                recorded_at=datetime.now(UTC),
            ),
            HistoryEntry(
                role="user",
                blocks=(TextBlock(text="now overflow"),),
                recorded_at=datetime.now(UTC),
            ),
        ]
    )
    assert compact_history(reference, keep_last=2) is True
    ref_marker = reference.snapshot()[0].blocks[0]
    assert isinstance(ref_marker, SummaryMarkerBlock)
    assert marker_block.digest == ref_marker.digest


# --- FAIL-SAFE: a broken summarizer never breaks the run ---------------------


@pytest.mark.parametrize(
    "summarizer",
    [
        ScriptedModel(
            script=[ScriptedFailure(error=RuntimeError("boom"))],
            context_capacity=100_000,
        ),
        ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="")])],
            context_capacity=100_000,
        ),
        ScriptedModel(script=[ScriptedOverflow()], context_capacity=100_000),
    ],
    ids=["raises", "empty", "overflow"],
)
async def test_failing_summarizer_falls_back_and_run_continues(
    summarizer: ScriptedModel, tmp_path: Path
) -> None:
    sink, history, _ = await _drive_to_reactive_compaction(
        summarizer=summarizer, tmp_path=tmp_path
    )
    # The run completed normally (no summarizer-caused unrecoverable-error)...
    assert sink.reasons[-1] == "natural-completion"
    # ...and the mechanical digest stands (excerpts present, not a model summary).
    excerpts = _marker_excerpts(history)
    assert excerpts and excerpts != [_SUMMARY]


async def test_timeout_summarizer_falls_back_and_run_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the guard so the test does not wait the full production default; the
    # behavior under test (a hung summarizer degrades to the mechanical digest and
    # the run still completes) is identical.
    monkeypatch.setattr(
        "loopplane.loop.summarizer.DEFAULT_SUMMARIZER_TIMEOUT_SECONDS", 0.1
    )
    slow = _SlowSummarizer()
    sink, history, _ = await _drive_to_reactive_compaction(
        summarizer=slow, tmp_path=tmp_path
    )
    assert slow.called  # the summarizer was consulted and then guarded out
    assert sink.reasons[-1] == "natural-completion"
    excerpts = _marker_excerpts(history)
    assert excerpts and excerpts != [_SUMMARY]


# --- config wiring: round-trip + no-secret (Contract C9) ---------------------


def test_compaction_summarizer_round_trips_from_mapping_and_defaults_none() -> None:
    summarizer = ScriptedModel(script=[], context_capacity=1_000)
    config = RuntimeConfig.from_mapping(
        {
            "model": ScriptedModel(script=[], context_capacity=1_000),
            "compaction_summarizer": summarizer,
        }
    )
    assert config.compaction_summarizer is summarizer
    default = RuntimeConfig.from_mapping(
        {"model": ScriptedModel(script=[], context_capacity=1_000)}
    )
    assert default.compaction_summarizer is None


def test_compaction_summarizer_is_not_a_secret_field() -> None:
    names = {f.name for f in dataclasses.fields(RuntimeConfig)}
    assert "compaction_summarizer" in names
    secrets = {"api_key", "token", "secret", "password", "credential"}
    assert not (names & secrets)


# --- proactive compaction (spec 041 threshold) also summarizes ---------------


async def test_proactive_compaction_uses_model_summary(tmp_path: Path) -> None:
    """The proactive threshold trigger (spec 041) also runs the summarizer overlay:
    grow the history past `threshold * capacity` and assert the model summary lands
    in the marker (no overflow needed)."""
    # Proactive compaction fires on several turns as the history grows, so the
    # summarizer is consulted repeatedly; give it a turn for each.
    summarizer = _RecordingSummarizer(
        ScriptedModel(
            script=[
                ScriptedTurn(increments=[TextIncrement(text=_SUMMARY)])
                for _ in range(10)
            ],
            context_capacity=100_000,
        )
    )
    script = [
        ScriptedTurn(increments=[TextIncrement(text="a sufficiently long answer " * 6)])
        for _ in range(5)
    ]
    model = ScriptedModel(script=script, context_capacity=200)
    controller = RuntimeController(
        model=model,
        gateway=ToolGateway(),
        event_sink=_Collector(),
        enable_assembly=True,
        assembly_keep_last=2,
        auto_compact_threshold=0.5,
        compaction_summarizer=summarizer,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    for i in range(5):
        await controller.drive(session_id, [TextBlock(text=f"prompt number {i} " * 4)])
    history = controller._require(session_id).history
    assert _marker_excerpts(history) == [_SUMMARY]
    assert summarizer.requests
