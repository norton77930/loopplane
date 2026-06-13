"""Contract tests for Memory (contracts/memory.md).

Asserts scan resilience (FR-071), deterministic selection with fallback
(FR-072), Gateway-governed write-tool semantics (FR-074), and verbatim
durable history under assembly-time injection (FR-073).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.memory import (
    MemoryAugmentation,
    MemoryEntry,
    MemoryStore,
    select_entries,
)
from loopplane.model import ToolCallRequest
from loopplane.tools import InternalToolAdapter

pytestmark = pytest.mark.anyio


def _seed(
    directory: Path, name: str, *, entry_type: str, description: str, body: str
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": entry_type,
        "name": name,
        "description": description,
        "body": body,
    }
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)


# --- scan resilience (FR-071) ----------------------------------------------------


def test_scan_skips_malformed_entries_and_reports_them(tmp_path: Path) -> None:
    _seed(tmp_path, "alpha", entry_type="project", description="about alpha", body="A")
    _seed(tmp_path, "beta", entry_type="user", description="about beta", body="B")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "incomplete.json").write_text(
        json.dumps({"name": "no-description"}), encoding="utf-8"
    )

    store = MemoryStore(tmp_path)
    entries, problems = store.scan()

    assert {entry.name for entry in entries} == {"alpha", "beta"}
    assert len(problems) == 2


def test_scan_of_a_missing_directory_is_empty_not_an_error(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "never-created")
    entries, problems = store.scan()
    assert entries == [] and problems == []


# --- deterministic selection (FR-072, research A5) ---------------------------------


def _entry(name: str, entry_type: str, description: str) -> MemoryEntry:
    return MemoryEntry(type=entry_type, name=name, description=description, body=name)


def test_selection_ranks_by_lexical_overlap_with_the_prompt() -> None:
    entries = [
        _entry("deploy-notes", "reference", "how to deploy the service"),
        _entry("style-guide", "reference", "code formatting conventions"),
    ]

    selected = select_entries(entries, "how do I deploy this?", limit=1)

    assert [entry.name for entry in selected] == ["deploy-notes"]


def test_selection_is_deterministic_with_stable_tie_breaking() -> None:
    entries = [
        _entry("zeta", "reference", "common topic"),
        _entry("alpha", "user", "common topic"),
        _entry("midd", "project", "common topic"),
    ]

    first = select_entries(entries, "tell me about the topic", limit=3)
    second = select_entries(list(reversed(entries)), "tell me about the topic", limit=3)

    # Equal scores break ties by type priority (user > project > reference),
    # then name — independent of input order.
    assert [e.name for e in first] == ["alpha", "midd", "zeta"]
    assert first == second


def test_no_signal_falls_back_to_type_priority_ordering() -> None:
    entries = [
        _entry("ref-entry", "reference", "completely unrelated"),
        _entry("feedback-entry", "feedback", "completely unrelated"),
        _entry("user-entry", "user", "completely unrelated"),
        _entry("project-entry", "project", "completely unrelated"),
    ]

    selected = select_entries(entries, "xyzzy quux", limit=4)

    assert [e.type for e in selected] == ["user", "project", "reference", "feedback"]


# --- the write tool (FR-074) --------------------------------------------------------


async def test_memory_write_tool_is_gateway_governed_and_immediately_visible(
    tmp_path: Path,
) -> None:
    store = MemoryStore(tmp_path / "memory")
    gateway = ToolGateway()
    gateway.register_adapter(InternalToolAdapter(memory_store=store))

    context = RunContext(session_id="s1", working_scope=tmp_path)
    emitter = EventEmitter(
        session_id="s1", sequencer=EventSequencer(), sink=_Collector()
    )

    (result,) = await gateway.execute_batch(
        [
            ToolCallRequest(
                call_id="c1",
                tool_name="memory_write",
                input={
                    "type": "project",
                    "name": "team-style",
                    "description": "preferred code style",
                    "body": "use spaces",
                },
            )
        ],
        parallel=False,
        context=context,
        emitter=emitter,
    )

    assert result.outcome == "success"
    entries, _ = store.scan()
    assert any(e.name == "team-style" and e.body == "use spaces" for e in entries)

    # Updates are idempotent by name and immediately visible.
    (updated,) = await gateway.execute_batch(
        [
            ToolCallRequest(
                call_id="c2",
                tool_name="memory_write",
                input={
                    "type": "project",
                    "name": "team-style",
                    "description": "preferred code style",
                    "body": "use tabs after all",
                },
            )
        ],
        parallel=False,
        context=context,
        emitter=emitter,
    )
    assert updated.outcome == "success"
    entries, _ = store.scan()
    matching = [e for e in entries if e.name == "team-style"]
    assert len(matching) == 1
    assert matching[0].body == "use tabs after all"


async def test_memory_write_rejects_undeclared_parameters(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    gateway = ToolGateway()
    gateway.register_adapter(InternalToolAdapter(memory_store=store))

    (result,) = await gateway.execute_batch(
        [
            ToolCallRequest(
                call_id="c1",
                tool_name="memory_write",
                input={
                    "type": "project",
                    "name": "x",
                    "description": "d",
                    "body": "b",
                    "privileged": True,
                },
            )
        ],
        parallel=False,
        context=RunContext(session_id="s1", working_scope=tmp_path),
        emitter=EventEmitter(
            session_id="s1", sequencer=EventSequencer(), sink=_Collector()
        ),
    )

    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "validation"


# --- assembly-time injection only (FR-073) -------------------------------------------


def test_memory_augmentation_provides_content_without_touching_history(
    tmp_path: Path,
) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write(
        MemoryEntry(
            type="project",
            name="deploy-notes",
            description="how to deploy the service",
            body="always run the smoke test first",
        )
    )
    augmentation = MemoryAugmentation(store, limit=3)

    text = augmentation.augment_for("how do I deploy?")

    assert text is not None
    assert "always run the smoke test first" in text
    # Re-establishment after compaction is a no-op for memory: every turn
    # re-selects from the store.
    assert augmentation.re_establish() is None
