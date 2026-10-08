"""Deterministic, public-safe test helpers for the dynamic-subagents unit (spec 043).

Credential-free and offline: a scripted parent model plus a scripted child model are the
only instruments, mirroring ``tests/orchestration_helpers.py`` (the one-shot subagent
``LoopDefinition``) and ``tests/integration/conftest.py`` (the controller harness).

The ``CountingChildHostFactory`` records every ``build_child_host`` call so a test can
prove that a capped spawn builds **zero** child hosts (no unbounded nesting).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.host.config import ToolSpec
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextIncrement,
)
from loopplane.tools.subagent import SpawnSubagentAdapter


class EventCollector:
    """An event sink that records every emitted event in order."""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]

    def of_type(self, event_type: str) -> list[RuntimeEvent]:
        return [event for event in self.events if event.type == event_type]


def child_host(
    child_script: Sequence[ScriptEntry],
    *,
    working_scope: Path,
    subagent_depth: int,
    config: RuntimeConfig | None = None,
) -> LoopPlaneHost:
    """A child ``LoopPlaneHost`` over a scripted child model, assembled at the given
    recursion depth. A fresh host per call gives the child run its own session."""

    model = ScriptedModel(script=list(child_script), context_capacity=100_000)
    child_config = config if config is not None else RuntimeConfig(model=model)
    return LoopPlaneHost(
        child_config, working_scope=working_scope, subagent_depth=subagent_depth
    )


def text_child_script(text: str) -> list[ScriptEntry]:
    """A one-turn child script that emits ``text`` as its final assistant message."""

    return [ScriptedTurn(increments=[TextIncrement(text=text)])]


@dataclass
class CountingChildHostFactory:
    """A ``build_child_host`` substitute that records each call (depth + allowlist) and
    returns a child host over a fixed child script. ``calls`` proves how many child
    hosts were built (zero when a spawn is denied at the cap)."""

    child_script: Sequence[ScriptEntry]
    nested_config: RuntimeConfig | None = None
    calls: list[tuple[int, tuple[str, ...] | None]] = field(default_factory=list)

    def __call__(
        self,
        depth: int,
        allowed_tools: tuple[str, ...] | None,
        working_scope: Path,
        fanout: object = None,
    ) -> LoopPlaneHost:
        del fanout
        self.calls.append((depth, allowed_tools))
        return child_host(
            self.child_script,
            working_scope=working_scope,
            subagent_depth=depth,
            config=self.nested_config,
        )


@dataclass
class ParentRuntime:
    controller: RuntimeController
    session_id: str
    collector: EventCollector
    factory: CountingChildHostFactory


def parent_runtime(
    parent_script: Sequence[ScriptEntry],
    *,
    tmp_path: Path,
    child_text: str = "child answer",
    child_script: Sequence[ScriptEntry] | None = None,
    nested_config: RuntimeConfig | None = None,
    max_subagent_depth: int = 1,
    parent_depth: int = 0,
    extra_tools: Sequence[ToolSpec] = (),
) -> ParentRuntime:
    """A parent ``RuntimeController`` over a scripted parent model with a
    ``SpawnSubagentAdapter`` wired to a counting child-host factory.

    ``parent_depth`` lets a test start the parent at the cap (to exercise the depth
    denial); ``nested_config`` lets a test give the child its own spawnable runtime."""

    model = ScriptedModel(script=list(parent_script), context_capacity=100_000)
    script = (
        list(child_script)
        if child_script is not None
        else text_child_script(child_text)
    )
    factory = CountingChildHostFactory(child_script=script, nested_config=nested_config)
    gateway = ToolGateway()
    for spec in extra_tools:
        gateway.register(spec.descriptor, spec.handler)
    gateway.register_adapter(
        SpawnSubagentAdapter(
            build_child_host=factory, max_subagent_depth=max_subagent_depth
        )
    )
    collector = EventCollector()
    controller = RuntimeController(
        model=model,
        gateway=gateway,
        event_sink=collector,
        subagent_depth=parent_depth,
    )
    session_id = controller.create_session(working_scope=tmp_path)
    return ParentRuntime(
        controller=controller,
        session_id=session_id,
        collector=collector,
        factory=factory,
    )
