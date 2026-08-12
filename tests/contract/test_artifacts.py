"""Contract tests for Artifact Storage (contracts/artifacts.md).

Asserts threshold offload with a bounded preview and stable reference,
retrieval by reference, and the aggregate replacement budget staying frozen
across resume (FR-090–FR-093).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.artifacts import ArtifactStore, ReplacementLedger
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.model import (
    OutputBlock,
    TextBlock,
    ToolCallRequest,
    ToolDescriptor,
)

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


async def test_offload_persists_full_content_and_returns_preview_and_reference(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path, preview_chars=64)
    big = "x" * 10_000

    reference, preview = await store.offload(
        session_id="s1", call_id="c1", outputs=[TextBlock(text=big)]
    )

    assert reference
    assert len(preview) < len(big)
    assert store.retrieve("s1", reference) == big

    metadata = store.metadata("s1", reference)
    assert metadata is not None
    assert metadata.call_id == "c1"
    assert metadata.size == len(big.encode("utf-8"))
    assert metadata.media_kind == "text"


def test_unknown_reference_is_a_normal_not_found(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.retrieve("s1", "never-issued") is None
    assert store.metadata("s1", "never-issued") is None


async def test_gateway_offloads_oversized_results_through_the_handoff(
    tmp_path: Path,
) -> None:
    """Acceptance 3.3 at the gateway seam: the full output is preserved as
    an artifact and the result carries preview + stable reference (FR-090,
    FR-091).
    """
    artifact_store = ArtifactStore(tmp_path, preview_chars=64)

    async def handoff(
        call: ToolCallRequest, outputs: list[OutputBlock], context: RunContext
    ) -> tuple[str, str]:
        return await artifact_store.offload(
            session_id=context.session_id, call_id=call.call_id, outputs=outputs
        )

    big = "line of output\n" * 2_000

    async def big_tool(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        return [TextBlock(text=big)]

    gateway = ToolGateway(output_limit_bytes=512, artifact_handoff=handoff)
    gateway.register(
        ToolDescriptor(
            name="big",
            description="produces a lot of output",
            input_schema={"type": "object"},
        ),
        big_tool,
    )

    results = await gateway.execute_batch(
        [ToolCallRequest(call_id="c1", tool_name="big", input={})],
        parallel=False,
        context=RunContext(session_id="s1", working_scope=tmp_path),
        emitter=EventEmitter(
            session_id="s1", sequencer=EventSequencer(), sink=_Collector()
        ),
    )

    (result,) = results
    assert result.outcome == "success"
    assert result.artifact_reference is not None
    preview_text = "".join(
        block.text for block in result.outputs if isinstance(block, TextBlock)
    )
    assert len(preview_text) < len(big)
    assert artifact_store.retrieve("s1", result.artifact_reference) == big


async def test_session_cleanup_does_not_unlink_through_mutable_parent_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detached cleanup must anchor deletion to opened, no-follow directories."""

    store = ArtifactStore(tmp_path)
    await store.offload(
        session_id="s1",
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )
    original_unlink = Path.unlink

    def reject_quarantine_path_unlink(path: Path, missing_ok: bool = False) -> None:
        if ".d" in path.parts:
            raise AssertionError("quarantine member deletion used pathname resolution")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", reject_quarantine_path_unlink)

    store.delete_session("s1")

    assert (tmp_path / "s1").exists() is False


async def test_replacement_budget_replaces_largest_results_first(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path, preview_chars=32)
    ledger = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")

    assert await ledger.track("small", [TextBlock(text="s" * 100)]) == []
    assert await ledger.track("medium", [TextBlock(text="m" * 150)]) == []
    decisions = await ledger.track("large", [TextBlock(text="L" * 200)])

    assert decisions, "exceeding the budget must produce replacement decisions"
    assert decisions[0].replaced_call_id == "large"
    assert len(decisions[0].preview) < 200
    assert store.retrieve("s1", decisions[0].artifact_reference) == "L" * 200


async def test_replacement_decisions_are_frozen_across_resume(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, preview_chars=32)
    ledger = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")
    await ledger.track("a", [TextBlock(text="a" * 200)])
    decisions = list(await ledger.track("b", [TextBlock(text="b" * 250)]))
    assert decisions

    # Resume: a fresh ledger restores the recorded decisions instead of
    # re-deciding; the replacement state reproduces exactly (FR-092).
    resumed = ReplacementLedger(budget_bytes=300, store=store, session_id="s1")
    resumed.restore(ledger.decisions)

    assert resumed.decisions == ledger.decisions
    assert {d.replaced_call_id for d in resumed.decisions} == {
        d.replaced_call_id for d in ledger.decisions
    }
