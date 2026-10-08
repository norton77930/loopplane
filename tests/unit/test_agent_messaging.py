"""Agent-to-agent messaging & swarm tool tests (spec 050; ADR 0003). Offline +
deterministic (a fake ``run_member`` injected directly — no real child runs)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext
from loopplane.context import SwarmSupervisor as SwarmSupervisorProto
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.host.assembly import _make_member_host_builder, assemble
from loopplane.host.config import RuntimeConfig
from loopplane.model.boundary import ModelIncrement, ModelRequest
from loopplane.model.content import TextBlock
from loopplane.tools.messaging import (
    COORDINATOR,
    Message,
    SwarmSupervisor,
    SwarmToolsAdapter,
)

pytestmark = pytest.mark.anyio


async def _settle() -> None:
    for _ in range(10):
        await anyio.sleep(0)


def _completing(text: str = "done"):
    async def run_member(
        supervisor: SwarmSupervisorProto,
        member_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: object = None,
    ) -> str:
        del fanout
        return f"{text}:{instruction}"

    return run_member


async def _raising_member(
    supervisor: SwarmSupervisorProto,
    member_id: str,
    instruction: str,
    allowed_tools: tuple[str, ...] | None,
    child_depth: int,
    working_scope: Path,
    fanout: object = None,
) -> str:
    del fanout
    raise RuntimeError("boom in the member run")


async def _hanging_member(
    supervisor: SwarmSupervisorProto,
    member_id: str,
    instruction: str,
    allowed_tools: tuple[str, ...] | None,
    child_depth: int,
    working_scope: Path,
    fanout: object = None,
) -> str:
    del fanout
    await anyio.Event().wait()  # never returns until cancelled
    return ""


def _ctx(
    supervisor: SwarmSupervisor | None, *, depth: int = 0, member_id: str | None = None
) -> RunContext:
    return RunContext(
        session_id="s",
        working_scope=Path("."),
        subagent_depth=depth,
        swarm=supervisor,
        swarm_member_id=member_id,
    )


async def _invoke(
    adapter: SwarmToolsAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


# --- US1: dispatch a team & collect replies ----------------------------------


async def test_dispatch_returns_id_and_collects_reply() -> None:
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing("R"), max_members=3, max_messages=10
        )
        mid = sup.dispatch(
            "job", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert mid is not None
        await _settle()
    member = sup.get(mid)
    assert member is not None
    assert member.status == "completed" and member.reply == "R:job"


async def test_failing_member_is_contained() -> None:
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_raising_member, max_members=3, max_messages=10
        )
        ok = sup.dispatch(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        bad = sup.dispatch(
            "b", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        await _settle()
    assert ok is not None and bad is not None
    bad_member = sup.get(bad)
    assert bad_member is not None
    assert bad_member.status == "failed" and bad_member.reply == "swarm member failed"


async def test_adapter_dispatch_returns_id_nonblocking() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        (started,) = await _invoke(
            adapter, "swarm_dispatch", {"instruction": "job"}, _ctx(sup)
        )
        assert isinstance(started, TextBlock) and "member dispatched" in started.text
        await _settle()


# --- US2: agents exchange messages -------------------------------------------


async def test_send_and_inbox_registry() -> None:
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        mid = sup.dispatch(
            "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert mid is not None
        await _settle()
        assert sup.send("coordinator", mid, "hello") == "ok"
        box = sup.inbox(mid)
        assert len(box) == 1
        assert box[0].content == "hello" and box[0].from_id == "coordinator"


async def test_member_to_member_messaging_via_adapter() -> None:
    # The coordinator sends to a member; the member (self resolved from
    # swarm_member_id) reads its inbox.
    adapter = SwarmToolsAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        mid = sup.dispatch(
            "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert mid is not None
        await _settle()
        (sent,) = await _invoke(
            adapter, "message_send", {"to": mid, "content": "ping B"}, _ctx(sup)
        )
        assert isinstance(sent, TextBlock) and "message sent" in sent.text
        (read,) = await _invoke(adapter, "message_inbox", {}, _ctx(sup, member_id=mid))
        assert isinstance(read, TextBlock)
        assert "ping B" in read.text and "coordinator" in read.text


async def test_get_and_list_report_metadata() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        mid = sup.dispatch(
            "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert mid is not None
        await _settle()
        (listing,) = await _invoke(adapter, "swarm_list", {}, _ctx(sup))
        assert isinstance(listing, TextBlock) and mid in listing.text
        (got,) = await _invoke(adapter, "swarm_get", {"member_id": mid}, _ctx(sup))
        assert isinstance(got, TextBlock) and "completed" in got.text


# --- US3: bounded, contained, lifecycle --------------------------------------


async def test_member_cap_denies_dispatch() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=1, max_messages=10
        )
        first = sup.dispatch(
            "a", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert first is not None
        (denied,) = await _invoke(
            adapter, "swarm_dispatch", {"instruction": "b"}, _ctx(sup)
        )
        assert isinstance(denied, ErrorOutput) and "cap" in denied.message
        await _settle()


async def test_message_cap_denies_send() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=1
        )
        mid = sup.dispatch(
            "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
        )
        assert mid is not None
        await _settle()
        assert sup.send("coordinator", mid, "one") == "ok"
        (denied,) = await _invoke(
            adapter, "message_send", {"to": mid, "content": "two"}, _ctx(sup)
        )
        assert isinstance(denied, ErrorOutput) and "cap" in denied.message


async def test_depth_cap_denies_dispatch() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=1)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        (denied,) = await _invoke(
            adapter, "swarm_dispatch", {"instruction": "x"}, _ctx(sup, depth=1)
        )
        assert isinstance(denied, ErrorOutput) and denied.category == "policy-denial"


async def test_unknown_recipient_and_member_are_clear_errors() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=2)
    async with anyio.create_task_group() as tg:
        sup = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=3, max_messages=10
        )
        (e1,) = await _invoke(
            adapter, "message_send", {"to": "nope", "content": "x"}, _ctx(sup)
        )
        assert isinstance(e1, ErrorOutput) and "unknown recipient" in e1.message
        (e2,) = await _invoke(adapter, "swarm_get", {"member_id": "nope"}, _ctx(sup))
        assert isinstance(e2, ErrorOutput) and e2.category == "validation"


async def test_running_member_cancelled_at_scope_exit() -> None:
    with anyio.fail_after(
        2
    ):  # a running member would hang the scope without cancel_all
        async with anyio.create_task_group() as tg:
            sup = SwarmSupervisor(
                task_group=tg,
                run_member=_hanging_member,
                max_members=3,
                max_messages=10,
            )
            mid = sup.dispatch(
                "x", allowed_tools=None, child_depth=1, working_scope=Path(".")
            )
            assert mid is not None
            await _settle()
            sup.cancel_all()
    member = sup.get(mid)
    assert member is not None and member.status == "cancelled"


async def test_adapter_errors_when_not_enabled() -> None:
    adapter = SwarmToolsAdapter(max_subagent_depth=1)
    (err,) = await _invoke(adapter, "swarm_dispatch", {"instruction": "x"}, _ctx(None))
    assert isinstance(err, ErrorOutput) and err.category == "validation"


# --- ADR 0003 D2: messages are NOT runtime events ----------------------------


def test_messages_are_not_runtime_events() -> None:
    # A Message is a plain in-run record (ADR 0003 D2): no event ``type`` discriminator
    # or sequence — it never flows on the runtime event bus.
    import dataclasses

    fields = {f.name for f in dataclasses.fields(Message)}
    assert fields == {"from_id", "to_id", "content"}
    msg = Message(from_id="a", to_id="b", content="c")
    assert not hasattr(msg, "type") and not hasattr(msg, "sequence")


# --- Member-host threading + default-off assembly ----------------------------


class _StubModel:
    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        return
        yield  # pragma: no cover - never run; makes this an async generator


async def test_member_host_carries_shared_supervisor_and_id() -> None:
    # The member-host builder bakes the SHARED supervisor + the member id into the child
    # host (so a member's run resolves "self" + reaches the shared registry; ADR 0003).
    config = RuntimeConfig(
        model=_StubModel(), max_swarm_members=2, max_subagent_depth=1
    )
    builder = _make_member_host_builder(config)
    sentinel = object()
    host = builder(sentinel, "m1", 1, None, Path("."), None)  # type: ignore[arg-type]
    assert host._swarm_supervisor is sentinel  # noqa: SLF001
    assert host._swarm_member_id == "m1"  # noqa: SLF001


async def test_default_off_registers_no_swarm_tools() -> None:
    assembled = assemble(RuntimeConfig(model=_StubModel()))
    names = {d.name for d in assembled.gateway.descriptors()}
    assert "swarm_dispatch" not in names


async def test_enabled_registers_the_five_tools() -> None:
    assembled = assemble(
        RuntimeConfig(model=_StubModel(), max_swarm_members=2, max_subagent_depth=1)
    )
    names = {d.name for d in assembled.gateway.descriptors()}
    assert {
        "swarm_dispatch",
        "swarm_get",
        "swarm_list",
        "message_send",
        "message_inbox",
    } <= names


async def test_oversize_send_is_denied_and_delivers_nothing() -> None:
    # 0 (the unset default) is no size cap: a message the count cap allows is delivered.
    # A positive cap denies an oversize send and does not deliver any of it.
    async with anyio.create_task_group() as tg:
        uncapped = SwarmSupervisor(
            task_group=tg, run_member=_completing(), max_members=1, max_messages=10
        )
        large = "x" * 50
        assert uncapped.send(COORDINATOR, COORDINATOR, large) == "ok"
        assert [message.content for message in uncapped.inbox(COORDINATOR)] == [large]

        capped = SwarmSupervisor(
            task_group=tg,
            run_member=_completing(),
            max_members=1,
            max_messages=10,
            max_message_size=4,
        )
        assert capped.send(COORDINATOR, COORDINATOR, "tiny") == "ok"
        before = len(capped.inbox(COORDINATOR))
        assert capped.send(COORDINATOR, COORDINATOR, "too-big") == "cap_reached"
        assert [message.content for message in capped.inbox(COORDINATOR)] == ["tiny"]
        assert len(capped.inbox(COORDINATOR)) == before
