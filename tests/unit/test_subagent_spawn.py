"""Unit tests for model-driven one-shot subagent spawning (spec 043).

Deterministic and offline: a scripted parent model + a scripted child model, the
one-shot subagent ``LoopDefinition`` driven through the EXISTING ``run_loop``. Covers:
the spawn round-trip (the parent gets the child's final text); the hard depth cap DENIES
a spawn at/over ``max_subagent_depth`` with ZERO child runs (no unbounded nesting); a
failing/empty child is contained; a restricted ``allowed_tools`` child is honored; the
child's events never reach the parent's live bus; and the assembly gating.
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext, SubagentFanout
from loopplane.errors import ErrorCategory
from loopplane.events.envelope import ToolCallCompletedEvent
from loopplane.gateway.spi import ErrorOutput
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.host.assembly import (
    _make_child_host_builder,
    _make_member_host_builder,
    assemble,
)
from loopplane.host.config import ConfigError, ToolSpec
from loopplane.model import (
    ScriptedFailure,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)
from loopplane.model.content import OutputBlock
from loopplane.tools import InternalToolAdapter, SpawnSubagentAdapter
from loopplane.tools.scheduling import AnyioSleeper
from tests.subagent_helpers import (
    EventCollector,
    child_host,
    parent_runtime,
    text_child_script,
)

pytestmark = pytest.mark.anyio


def _spawn_call(call_id: str, task: str, **extra: object) -> ToolCallRequest:
    return ToolCallRequest(
        call_id=call_id,
        tool_name="spawn_subagent",
        input={"task": task, **extra},
    )


def _spawn_then_finish(task: str = "do it") -> list:
    """A parent that calls spawn_subagent, then (after the tool result) emits a final
    answer — so the parent run completes naturally after the spawn."""

    return [
        ScriptedTurn(increments=[_spawn_call("c1", task)], stop_reason="tool-use"),
        ScriptedTurn(increments=[TextIncrement(text="parent done")]),
    ]


def _spawn_completed_event(collector: object) -> ToolCallCompletedEvent:
    completed = [
        event
        for event in collector.of_type("tool-call-completed")  # type: ignore[attr-defined]
        if event.payload.call_id == "c1"
    ]
    assert len(completed) == 1, "expected exactly one spawn_subagent completion"
    event = completed[0]
    assert isinstance(event, ToolCallCompletedEvent)
    return event


def _output_text(outputs: list[OutputBlock]) -> str:
    return "".join(block.text for block in outputs if isinstance(block, TextBlock))


# --- US1: the model delegates a focused sub-task -----------------------------------


async def test_spawn_returns_child_final_text_to_parent(tmp_path: Path) -> None:
    runtime = parent_runtime(
        _spawn_then_finish(), tmp_path=tmp_path, child_text="the child answer"
    )

    await runtime.controller.drive(
        runtime.session_id, [TextBlock(text="please delegate")]
    )

    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "success"
    assert "the child answer" in _output_text(event.payload.outputs)
    # Exactly one child host was built (one-shot), at depth 1 (parent 0 + 1).
    assert runtime.factory.calls == [(1, None)]
    # The parent run completed naturally after using the result.
    assert runtime.collector.events[-1].type == "run-terminated"
    assert runtime.collector.events[-1].payload.reason == "natural-completion"


async def test_spawn_descriptor_shape() -> None:
    adapter = SpawnSubagentAdapter(
        build_child_host=lambda depth, allowed, scope: None,  # type: ignore[arg-type,return-value]
        max_subagent_depth=1,
    )
    descriptors = list(adapter.describe())
    assert len(descriptors) == 1
    descriptor = descriptors[0]
    assert descriptor.name == "spawn_subagent"
    assert descriptor.read_only is False
    assert descriptor.network is False
    assert descriptor.input_schema["required"] == ["task"]
    properties = descriptor.input_schema["properties"]
    assert isinstance(properties, dict)
    assert "task" in properties and "allowed_tools" in properties


# --- US2: the hard recursion-depth cap (SAFETY) ------------------------------------


async def test_depth_cap_denies_spawn_with_zero_child_runs(tmp_path: Path) -> None:
    """At subagent_depth == max_subagent_depth the spawn is denied and NO child runs —
    proving subagents cannot nest without bound."""

    runtime = parent_runtime(
        _spawn_then_finish(),
        tmp_path=tmp_path,
        max_subagent_depth=1,
        parent_depth=1,  # already at the cap
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="try to spawn")])

    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "failure"
    assert event.payload.error is not None
    assert event.payload.error.category == ErrorCategory.POLICY_DENIAL
    assert "depth cap" in event.payload.error.reason
    # The safety invariant: ZERO child hosts built (no run started at the cap).
    assert runtime.factory.calls == []
    # The parent run is not crashed; it continues and completes.
    assert runtime.collector.events[-1].type == "run-terminated"


async def test_child_runs_at_parent_depth_plus_one(tmp_path: Path) -> None:
    runtime = parent_runtime(
        _spawn_then_finish(), tmp_path=tmp_path, max_subagent_depth=2, parent_depth=0
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    assert runtime.factory.calls == [(1, None)]


async def test_default_cap_one_blocks_a_grandchild(tmp_path: Path) -> None:
    """With max_subagent_depth=1, a child (depth 1) that itself tries to spawn is denied
    with zero grandchild runs."""

    # The child's runtime is itself spawn-capable (max_subagent_depth=1), and its model
    # tries to spawn a grandchild then answers.
    child_model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[_spawn_call("g1", "grandchild task")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="child answer")]),
        ],
        context_capacity=100_000,
    )
    # The child host is a real assembled host with spawning enabled (cap 1), so when it
    # runs at depth 1 it registers its own spawn tool but denies at depth 1 >= 1.
    nested_config = RuntimeConfig(model=child_model, max_subagent_depth=1)

    runtime = parent_runtime(
        _spawn_then_finish(),
        tmp_path=tmp_path,
        max_subagent_depth=1,
        parent_depth=0,
        child_script=[],  # unused: nested_config supplies the child model
        nested_config=nested_config,
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    # The top-level spawn (depth 0 -> child at depth 1) succeeds and returns the child's
    # answer; the child's own grandchild spawn was denied inside the child run, so the
    # child still produced "child answer".
    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "success"
    assert "child answer" in _output_text(event.payload.outputs)
    # The counting factory built exactly the one (depth-1) child host; the grandchild
    # was denied before any host build (the child's own assembled spawn adapter denied
    # it).
    assert runtime.factory.calls == [(1, None)]


# --- US3: a failing child is contained ---------------------------------------------


async def test_raising_child_is_contained(tmp_path: Path) -> None:
    runtime = parent_runtime(
        _spawn_then_finish(),
        tmp_path=tmp_path,
        child_script=[ScriptedFailure(error=RuntimeError("boom secret detail"))],
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "failure"
    assert event.payload.error is not None
    # Public-safe: no raw exception text leaks.
    assert "boom secret detail" not in event.payload.error.reason
    assert "Traceback" not in event.payload.error.reason
    # The parent did not crash; it took its next turn and completed.
    assert runtime.collector.events[-1].type == "run-terminated"
    assert runtime.collector.events[-1].payload.reason == "natural-completion"


async def test_empty_answer_child_is_contained(tmp_path: Path) -> None:
    # A child that ends its turn with no text at all.
    runtime = parent_runtime(
        _spawn_then_finish(),
        tmp_path=tmp_path,
        child_script=[ScriptedTurn(increments=[])],
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "failure"
    assert event.payload.error is not None
    assert event.payload.error.reason  # a clear, non-empty normalized message
    # Never a crash.
    assert runtime.collector.events[-1].type == "run-terminated"


# --- US4: restricted toolset + events isolation ------------------------------------


def _noop_tool(name: str) -> ToolSpec:
    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        return [TextBlock(text=name)]

    descriptor = ToolDescriptor(
        name=name,
        description=name,
        input_schema={"type": "object", "properties": {}, "additionalProperties": True},
    )
    return ToolSpec(descriptor=descriptor, handler=handler)


async def test_restricted_allowed_tools_filters_child_toolset(tmp_path: Path) -> None:
    """A child spawned with allowed_tools sees only the allowlisted tools (FR-040): a
    host-declared tool outside the allowlist is absent, and a multi-tool adapter that
    advertises none of those names is omitted."""

    parent_config = RuntimeConfig(
        model=ScriptedModel(script=[], context_capacity=100_000),
        tools=(_noop_tool("alpha"), _noop_tool("beta")),
        # None of this adapter's tools are allowlisted, so it is omitted.
        tool_adapters=(InternalToolAdapter(),),
        max_subagent_depth=1,
    )
    from loopplane.host.assembly import _restrict_config

    child_config = _restrict_config(parent_config, ("alpha",))
    child_host = LoopPlaneHost(child_config, working_scope=tmp_path, subagent_depth=1)
    tool_names = {info.name for info in child_host.inspect_tools()}

    assert "alpha" in tool_names
    assert "beta" not in tool_names
    # The internal adapter advertised nothing on the allowlist, so it is omitted.
    assert "read_file" not in tool_names
    assert "write_file" not in tool_names
    # spawn_subagent is not re-granted to the restricted child (not in the allowlist).
    assert "spawn_subagent" not in tool_names


async def test_allowed_tools_intersects_a_multi_tool_adapter(tmp_path: Path) -> None:
    """A named tool on a multi-tool adapter stays; every other tool on it is omitted.

    ``spawn_subagent`` stays absent unless the allowlist names it. Invoking a
    non-allowlisted name cannot run.
    """

    parent_config = RuntimeConfig(
        model=ScriptedModel(script=[], context_capacity=100_000),
        tool_adapters=(InternalToolAdapter(),),
        max_subagent_depth=1,
    )
    from loopplane.gateway import ErrorOutput
    from loopplane.host.assembly import _restrict_config

    child_config = _restrict_config(parent_config, ("read_file",))
    child_host = LoopPlaneHost(child_config, working_scope=tmp_path, subagent_depth=1)
    tool_names = {info.name for info in child_host.inspect_tools()}
    internal = {descriptor.name for descriptor in InternalToolAdapter().describe()}

    assert "read_file" in tool_names
    assert "write_file" not in tool_names
    assert tool_names.isdisjoint(internal - {"read_file"})
    assert "spawn_subagent" not in tool_names

    assert len(child_config.tool_adapters) == 1
    adapter = child_config.tool_adapters[0]
    context = RunContext(session_id="s", working_scope=tmp_path)
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    read_outputs = [
        item
        async for item in adapter.invoke("read_file", {"path": "note.txt"}, context)
    ]
    assert any(
        isinstance(item, TextBlock) and item.text == "hello" for item in read_outputs
    )

    denied = [
        item
        async for item in adapter.invoke(
            "write_file", {"path": "secret.txt", "content": "nope"}, context
        )
    ]
    assert not (tmp_path / "secret.txt").exists()
    assert denied and all(isinstance(item, ErrorOutput) for item in denied)


async def test_unrestricted_child_inherits_parent_tools(tmp_path: Path) -> None:
    parent_config = RuntimeConfig(
        model=ScriptedModel(script=[], context_capacity=100_000),
        tool_adapters=(InternalToolAdapter(),),
        max_subagent_depth=2,
    )
    from loopplane.host.assembly import _restrict_config

    child_config = _restrict_config(parent_config, None)
    child_host = LoopPlaneHost(child_config, working_scope=tmp_path, subagent_depth=1)
    tool_names = {info.name for info in child_host.inspect_tools()}

    assert {"read_file", "write_file"} <= tool_names


async def test_child_events_not_on_parent_live_bus(tmp_path: Path) -> None:
    """The child's loop events are captured (metadata only) and never re-emitted onto
    the parent's live event bus (Constitution VI)."""

    runtime = parent_runtime(
        _spawn_then_finish(), tmp_path=tmp_path, child_text="child answer"
    )

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    parent_session = runtime.session_id
    # Every event the parent bus saw belongs to the PARENT session only — no child
    # session's events leaked onto the parent's live stream.
    foreign = [
        event
        for event in runtime.collector.events
        if event.session_id != parent_session
    ]
    assert foreign == []
    # The child's metadata-only event summary rode in the tool result text instead.
    event = _spawn_completed_event(runtime.collector)
    assert "loop events" in _output_text(event.payload.outputs)


# --- Assembly gating ----------------------------------------------------------------


def test_spawn_tool_registered_only_when_cap_enabled(tmp_path: Path) -> None:
    model = ScriptedModel(script=[], context_capacity=100_000)

    enabled = LoopPlaneHost(
        RuntimeConfig(model=model, max_subagent_depth=1), working_scope=tmp_path
    )
    assert "spawn_subagent" in {info.name for info in enabled.inspect_tools()}

    disabled = LoopPlaneHost(
        RuntimeConfig(model=model, max_subagent_depth=0), working_scope=tmp_path
    )
    assert "spawn_subagent" not in {info.name for info in disabled.inspect_tools()}


async def test_missing_task_is_a_validation_error_with_no_child_run(
    tmp_path: Path,
) -> None:
    # The gateway validates the schema before any run; a call missing `task` is
    # rejected with a normalized validation error and no child run starts.
    parent_script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(call_id="c1", tool_name="spawn_subagent", input={})
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="parent done")]),
    ]
    runtime = parent_runtime(parent_script, tmp_path=tmp_path)

    await runtime.controller.drive(runtime.session_id, [TextBlock(text="spawn")])

    event = _spawn_completed_event(runtime.collector)
    assert event.payload.outcome == "failure"
    assert event.payload.error is not None
    assert event.payload.error.category == ErrorCategory.VALIDATION
    assert runtime.factory.calls == []


async def test_fanout_cap_stops_the_second_spawn_in_the_tree(tmp_path: Path) -> None:
    """One tree may start only the configured number of spawn_subagent children."""

    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[_spawn_call("c1", "child task")], stop_reason="tool-use"
            ),
            ScriptedTurn(
                increments=[_spawn_call("g1", "grandchild task")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="child answer")]),
            ScriptedTurn(increments=[TextIncrement(text="parent done")]),
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(
        RuntimeConfig(model=model, max_subagent_depth=2, max_subagent_fanout=1),
        working_scope=tmp_path,
    )
    collector = EventCollector()
    outcome = await host.run("delegate", on_event=collector)
    event = _spawn_completed_event(collector)
    assert event.payload.outcome == "success"
    assert "child answer" in _output_text(event.payload.outputs)
    assert "grandchild task" not in _output_text(event.payload.outputs)
    assert outcome.termination_reason == "natural-completion"


async def test_fanout_denial_builds_no_child_and_hides_the_task(tmp_path: Path) -> None:
    calls: list[int] = []

    def factory(
        depth: int,
        allowed: tuple[str, ...] | None,
        scope: Path,
        fanout: object = None,
    ) -> LoopPlaneHost:
        del fanout
        calls.append(depth)
        return child_host(
            text_child_script("ok"), working_scope=scope, subagent_depth=depth
        )

    adapter = SpawnSubagentAdapter(
        build_child_host=factory,
        max_subagent_depth=2,
    )
    context = RunContext(
        session_id="s",
        working_scope=tmp_path,
        subagent_depth=0,
        subagent_fanout=SubagentFanout(1),
    )

    async def collect(task: str) -> list[object]:
        return [
            item
            async for item in adapter.invoke("spawn_subagent", {"task": task}, context)
        ]

    first = await collect("one")
    second = await collect("secret socket task")
    assert calls == [1]
    assert any(isinstance(item, TextBlock) for item in first)
    errors = [item for item in second if isinstance(item, ErrorOutput)]
    assert len(errors) == 1
    assert errors[0].category == ErrorCategory.POLICY_DENIAL
    assert str(errors[0].message) == (
        "subagent fan-out cap reached (1); refusing to spawn a subagent"
    )
    assert "secret socket" not in str(errors[0].message)


async def test_unset_fanout_still_starts_a_grandchild(tmp_path: Path) -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[_spawn_call("c1", "child task")], stop_reason="tool-use"
            ),
            ScriptedTurn(
                increments=[_spawn_call("g1", "grandchild task")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="grandchild answer")]),
            ScriptedTurn(increments=[TextIncrement(text="child answer")]),
            ScriptedTurn(increments=[TextIncrement(text="parent done")]),
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(
        RuntimeConfig(model=model, max_subagent_depth=2),
        working_scope=tmp_path,
    )
    collector = EventCollector()
    outcome = await host.run("delegate", on_event=collector)
    event = _spawn_completed_event(collector)
    assert event.payload.outcome == "success"
    text = _output_text(event.payload.outputs)
    assert "child answer" in text
    assert "grandchild answer" not in text
    assert outcome.termination_reason == "natural-completion"


async def test_fanout_resets_on_the_next_run(tmp_path: Path) -> None:
    """The same host gets a fresh count on the next run."""

    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[_spawn_call("c1", "first child")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="first child answer")]),
            ScriptedTurn(increments=[TextIncrement(text="first parent done")]),
            ScriptedTurn(
                increments=[_spawn_call("c1", "second child")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="second child answer")]),
            ScriptedTurn(increments=[TextIncrement(text="second parent done")]),
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(
        RuntimeConfig(model=model, max_subagent_depth=1, max_subagent_fanout=1),
        working_scope=tmp_path,
    )
    first = EventCollector()
    first_outcome = await host.run("first", on_event=first)
    first_event = _spawn_completed_event(first)
    assert first_event.payload.outcome == "success"
    assert "first child answer" in _output_text(first_event.payload.outputs)
    assert first_outcome.termination_reason == "natural-completion"

    second = EventCollector()
    second_outcome = await host.run("second", on_event=second)
    second_event = _spawn_completed_event(second)
    assert second_event.payload.outcome == "success"
    assert "second child answer" in _output_text(second_event.payload.outputs)
    assert second_outcome.termination_reason == "natural-completion"


def test_negative_fanout_is_rejected(tmp_path: Path) -> None:
    model = ScriptedModel(script=[], context_capacity=100_000)
    with pytest.raises(ConfigError, match="max_subagent_fanout"):
        LoopPlaneHost(
            RuntimeConfig(model=model, max_subagent_fanout=-1),
            working_scope=tmp_path,
        )


async def test_depth_denial_does_not_consume_a_spawn_slot(tmp_path: Path) -> None:
    calls: list[int] = []

    def factory(
        depth: int,
        allowed: tuple[str, ...] | None,
        scope: Path,
        fanout: object = None,
    ) -> LoopPlaneHost:
        del fanout
        calls.append(depth)
        return child_host(
            text_child_script("ok"), working_scope=scope, subagent_depth=depth
        )

    counter = SubagentFanout(1)
    adapter = SpawnSubagentAdapter(
        build_child_host=factory,
        max_subagent_depth=1,
    )
    denied = RunContext(
        session_id="s",
        working_scope=tmp_path,
        subagent_depth=1,
        subagent_fanout=counter,
    )
    allowed = RunContext(
        session_id="s",
        working_scope=tmp_path,
        subagent_depth=0,
        subagent_fanout=counter,
    )

    async def collect(context: RunContext) -> list[object]:
        return [
            item
            async for item in adapter.invoke(
                "spawn_subagent", {"task": "secret socket task"}, context
            )
        ]

    first = await collect(denied)
    second = await collect(allowed)
    depth_errors = [item for item in first if isinstance(item, ErrorOutput)]
    assert len(depth_errors) == 1
    assert "depth cap" in str(depth_errors[0].message)
    assert "secret socket" not in str(depth_errors[0].message)
    assert calls == [1]
    assert any(isinstance(item, TextBlock) for item in second)


def test_from_mapping_fanout_is_unset_unless_given() -> None:
    model = ScriptedModel(script=[], context_capacity=100_000)
    unset = RuntimeConfig.from_mapping({"model": model})
    assert unset.max_subagent_fanout is None
    zero = RuntimeConfig.from_mapping({"model": model, "max_subagent_fanout": 0})
    assert zero.max_subagent_fanout == 0
    with pytest.raises(ConfigError, match="max_subagent_fanout"):
        RuntimeConfig.from_mapping({"model": model, "max_subagent_fanout": True})


async def test_zero_fanout_denies_every_spawn_and_hides_the_task(
    tmp_path: Path,
) -> None:
    calls: list[int] = []

    def factory(
        depth: int,
        allowed: tuple[str, ...] | None,
        scope: Path,
        fanout: object = None,
    ) -> LoopPlaneHost:
        del fanout
        calls.append(depth)
        return child_host(
            text_child_script("ok"), working_scope=scope, subagent_depth=depth
        )

    adapter = SpawnSubagentAdapter(
        build_child_host=factory,
        max_subagent_depth=2,
    )
    context = RunContext(
        session_id="s",
        working_scope=tmp_path,
        subagent_depth=0,
        subagent_fanout=SubagentFanout(0),
    )
    items = [
        item
        async for item in adapter.invoke(
            "spawn_subagent", {"task": "secret socket task"}, context
        )
    ]
    errors = [item for item in items if isinstance(item, ErrorOutput)]
    assert calls == []
    assert len(errors) == 1
    assert errors[0].category == ErrorCategory.POLICY_DENIAL
    assert str(errors[0].message) == (
        "subagent fan-out cap reached (0); refusing to spawn a subagent"
    )
    assert "secret socket" not in str(errors[0].message)


def test_a_foreign_fanout_object_is_rejected(tmp_path: Path) -> None:
    model = ScriptedModel(script=[], context_capacity=100_000)
    with pytest.raises(ConfigError, match="max_subagent_fanout"):
        LoopPlaneHost(
            RuntimeConfig(model=model, max_subagent_depth=1),
            working_scope=tmp_path,
            subagent_fanout=object(),  # type: ignore[arg-type]
        )


async def test_child_hosts_join_the_active_run_counter(tmp_path: Path) -> None:
    """A child built with the run's counter uses that object, not its config."""

    counter = SubagentFanout(0)

    def host_config() -> RuntimeConfig:
        model = ScriptedModel(
            script=[
                ScriptedTurn(
                    increments=[_spawn_call("c1", "secret socket task")],
                    stop_reason="tool-use",
                ),
                ScriptedTurn(increments=[TextIncrement(text="done")]),
            ],
            context_capacity=100_000,
        )
        return RuntimeConfig(
            model=model,
            max_subagent_depth=2,
            max_subagent_fanout=5,
            max_swarm_members=1,
        )

    child = _make_child_host_builder(host_config())(1, None, tmp_path, counter)
    member = _make_member_host_builder(host_config())(
        object(),  # type: ignore[arg-type]
        "m1",
        1,
        None,
        tmp_path,
        counter,
    )
    denial = "subagent fan-out cap reached (0); refusing to spawn a subagent"
    for host in (child, member):
        collector = EventCollector()
        outcome = await host.run("delegate", on_event=collector)
        event = _spawn_completed_event(collector)
        assert event.payload.outcome == "failure"
        assert event.payload.error is not None
        assert event.payload.error.reason == denial
        assert "secret socket" not in event.payload.error.reason
        assert outcome.termination_reason == "natural-completion"


async def test_late_schedule_child_keeps_the_run_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A schedule that builds its child after the parent run returns still uses
    that run's spawn counter."""

    gate = anyio.Event()

    async def wait_for_release(self: AnyioSleeper, seconds: float) -> None:
        del self, seconds
        await gate.wait()

    monkeypatch.setattr(AnyioSleeper, "sleep", wait_for_release)
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[_spawn_call("c1", "first child")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="first answer")]),
            ScriptedTurn(
                increments=[
                    ToolCallRequest(
                        call_id="s1",
                        tool_name="schedule_create",
                        input={
                            "instruction": "secret socket task",
                            "delay_seconds": 5,
                        },
                    )
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="parent done")]),
            ScriptedTurn(
                increments=[_spawn_call("c2", "secret socket task")],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="child finished")]),
        ],
        context_capacity=100_000,
    )
    assembled = assemble(
        RuntimeConfig(
            model=model,
            max_subagent_depth=2,
            max_subagent_fanout=1,
            max_schedules=1,
        )
    )
    session_id = assembled.controller.create_session(working_scope=tmp_path)
    async with anyio.create_task_group() as task_group:
        supervisor = assembled.controller.make_schedule_supervisor(task_group)
        assert supervisor is not None
        await assembled.controller.drive(
            session_id,
            [TextBlock(text="delegate")],
            schedule_supervisor=supervisor,
        )
        pending = supervisor.list_schedules()
        assert len(pending) == 1
        assert pending[0].status == "active"
        assert pending[0].last_result is None
        gate.set()
        record = pending[0]
        for _ in range(200):
            if record.status == "completed":
                break
            await anyio.sleep(0)
    assert record.status == "completed"
    assert record.last_result == "child finished"
    assert "secret socket" not in (record.last_result or "")
