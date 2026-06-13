"""Runnable example: begin a loop's input with recalled context.

Public-safe and credential-free. A scripted Loop State (prior runs + an artifact)
plus in-memory stores (an artifact reader, durable memory entries, a knowledge
index) feed conversation / artifact / memory / knowledge recall; the injection
policy composes them under a budget and prepends a bounded preamble to a base
input.

Run::

    python examples/recall_quickstart.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from loopplane.artifacts import ArtifactMeta
from loopplane.engineering import ArtifactRef, LoopState, RunReference, StaticInput
from loopplane.memory import MemoryEntry
from loopplane.recall import (
    InMemoryKnowledgeIndex,
    KnowledgeEntry,
    RetrievalBudget,
    artifact_recall,
    assemble_recall,
    build_recall_input,
    conversation_recall,
    knowledge_recall,
    memory_entry_recall,
)


class _InMemoryArtifactReader:
    """A minimal in-process ArtifactReader (the host's ArtifactStore plays this
    role in a real embedding)."""

    def __init__(self, metas: Sequence[ArtifactMeta]) -> None:
        self._by_key = {(meta.session_id, meta.reference): meta for meta in metas}

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None:
        return self._by_key.get((session_id, reference))


def run_demo() -> str:
    state = LoopState(
        loop_id="report-loop",
        loop_definition_id="report-def",
        iteration_index=2,
        run_refs=(
            RunReference("run-1", "natural-completion"),
            RunReference("run-2", "natural-completion"),
        ),
        artifacts=(ArtifactRef("run-2", "draft-001"),),
    )
    reader = _InMemoryArtifactReader(
        [
            ArtifactMeta(
                reference="draft-001",
                session_id="run-2",
                call_id="call-1",
                size=2048,
                media_kind="text",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        ]
    )
    entries = [
        MemoryEntry(
            type="reference",
            name="report-style",
            description="house report style guide",
            body="lead with the conclusion",
        ),
        MemoryEntry(
            type="reference",
            name="audience",
            description="executive readers",
            body="keep it brief",
        ),
    ]
    index = InMemoryKnowledgeIndex(
        [KnowledgeEntry("kb-report", "report templates and structure")]
    )

    sources = [
        conversation_recall(),
        artifact_recall(reader),
        memory_entry_recall(entries),
        knowledge_recall(index),
    ]
    budget = RetrievalBudget(max_entries=6, max_chars=600)

    assembly = assemble_recall(sources, budget, state=state)
    print("Recalled context:")
    for entry in assembly.entries:
        print(f"  [{entry.origin}] {entry.text}")
    print(f"dropped: {assembly.dropped}; skipped: {assembly.skipped}")

    recall_input = build_recall_input(
        StaticInput("write the quarterly report"), sources, budget, state=state
    )
    prompt = recall_input.initial()
    print("\nInjected loop input:\n")
    print(prompt)
    return prompt if isinstance(prompt, str) else ""


if __name__ == "__main__":
    run_demo()
