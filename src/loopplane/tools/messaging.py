"""Agent-to-agent messaging & swarm tools (spec 050; ADR 0003).

A ``SwarmSupervisor`` lets a coordinator agent dispatch work to a team of bounded member
child runs (reusing the unit-043/048 one-shot ``run_loop`` child) and collect their
replies, and lets members exchange messages. It owns an injected ``anyio`` task group, a
**member registry** (``member_id -> Member``), and a **message registry** (per-member
inboxes ``member_id -> list[Message]``).

SAFE + additive (ADR 0003): messages are a SEPARATE in-run registry, NOT runtime events,
so the Event Bus / ``SCHEMA_VERSION`` / content model are UNCHANGED (D2). Reuses the
unit-048/049 supervisor pattern (ADR 0002). Bounded (a team cap + a message cap + the
043 depth cap), contained (a failing member -> a public-safe marker, never a raise), and
lifecycle-bound (members cancelled when the supervisor's scope exits). Reached via
``RunContext.swarm``; a member resolves "self" from ``RunContext.swarm_member_id`` (the
top-level run is the reserved id ``"coordinator"``). Gateway-only (V); child events
captured, never on the parent bus (VI). Registered only when ``max_swarm_members >= 1``
(0 = off, byte-identical).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio

from loopplane.context import RunContext, SubagentFanout
from loopplane.context import SwarmSupervisor as _SwarmSupervisorProto
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.tools.background import make_run_child

if TYPE_CHECKING:
    from loopplane.host import LoopPlaneHost

MemberStatus = Literal["running", "completed", "failed", "cancelled"]
SendResult = Literal["ok", "unknown_recipient", "cap_reached"]

#: The reserved member id for the top-level (coordinator) run.
COORDINATOR = "coordinator"

_FAILED_MESSAGE = "swarm member failed"

# Builds a member's child host: (supervisor, member_id, depth, allowed_tools, scope) ->
# host. The supervisor passes itself + the member id so the member's child context gets
# the SHARED supervisor + its identity (the closure lives in the host assembly).
MemberHostFactory = Callable[
    [
        _SwarmSupervisorProto,
        str,
        int,
        "tuple[str, ...] | None",
        Path,
        SubagentFanout | None,
    ],
    "LoopPlaneHost",
]

# Runs one member child, returns its final text. The supervisor is passed so the run can
# build the member's child host with the shared supervisor baked in. The last argument
# is the spawn counter captured when the member was dispatched.
RunMember = Callable[
    [
        _SwarmSupervisorProto,
        str,
        str,
        "tuple[str, ...] | None",
        int,
        Path,
        SubagentFanout | None,
    ],
    Awaitable[str],
]


@dataclass
class Member:
    """One swarm member's registry record (metadata + reply; no payloads)."""

    id: str
    status: MemberStatus = "running"
    reply: str | None = None
    cancel_scope: anyio.CancelScope = field(default_factory=anyio.CancelScope)


@dataclass
class Message:
    """One agent-to-agent message (metadata-safe text; ADR 0003 — not an event)."""

    from_id: str
    to_id: str
    content: str


class SwarmSupervisor:
    """Owns the member scope + the member & message registries for one run/session."""

    def __init__(
        self,
        *,
        task_group: anyio.abc.TaskGroup,
        run_member: RunMember,
        max_members: int,
        max_messages: int,
        max_message_size: int = 0,
    ) -> None:
        self._task_group = task_group
        self._run_member_fn = run_member
        self._max_members = max_members
        self._max_messages = max_messages
        # 0 means no size cap, so an unset cap does not reject a message the
        # count cap already allows.
        self._max_message_size = max_message_size
        self._members: dict[str, Member] = {}
        self._inboxes: dict[str, list[Message]] = {COORDINATOR: []}

    def dispatch(
        self,
        instruction: str,
        *,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None = None,
    ) -> str | None:
        """Launch a member child run + return its id; ``None`` at the team-size cap.

        Non-blocking: the member runs via ``task_group.start_soon``; its record is
        ``running`` until it finishes (``completed`` / ``failed``) or is cancelled.
        ``fanout`` is the spawn counter captured at admit time.
        """

        if len(self._members) >= self._max_members:
            return None
        member_id = uuid.uuid4().hex
        self._members[member_id] = Member(id=member_id)
        self._inboxes.setdefault(member_id, [])
        self._task_group.start_soon(
            self._run_member,
            member_id,
            instruction,
            allowed_tools,
            child_depth,
            working_scope,
            fanout,
        )
        return member_id

    async def _run_member(
        self,
        member_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None,
    ) -> None:
        record = self._members[member_id]
        with record.cancel_scope:
            try:
                text = await self._run_member_fn(
                    self,
                    member_id,
                    instruction,
                    allowed_tools,
                    child_depth,
                    working_scope,
                    fanout,
                )
            except Exception:  # noqa: BLE001 - contained: never raise across the Gateway
                record.status = "failed"
                record.reply = _FAILED_MESSAGE
                return
            record.status = "completed" if text else "failed"
            record.reply = text or _FAILED_MESSAGE
            return
        # Reached only when the per-member scope was cancelled (cancel_all).
        if record.status == "running":
            record.status = "cancelled"

    def get(self, member_id: str) -> Member | None:
        return self._members.get(member_id)

    def list_members(self) -> list[Member]:
        return list(self._members.values())

    def send(self, from_id: str, to_id: str, content: str) -> SendResult:
        if to_id != COORDINATOR and to_id not in self._members:
            return "unknown_recipient"
        if self._max_message_size > 0 and len(content) > self._max_message_size:
            return "cap_reached"
        total = sum(len(inbox) for inbox in self._inboxes.values())
        if total >= self._max_messages:
            return "cap_reached"
        self._inboxes.setdefault(to_id, []).append(
            Message(from_id=from_id, to_id=to_id, content=content)
        )
        return "ok"

    def inbox(self, member_id: str) -> list[Message]:
        return list(self._inboxes.get(member_id, []))

    def cancel_all(self) -> None:
        """Cancel every still-running member (called at the run/session scope exit)."""
        for member in self._members.values():
            if member.status == "running":
                member.cancel_scope.cancel()
                member.status = "cancelled"


def _member_runner(build_member_host: MemberHostFactory) -> RunMember:
    """Wrap the member-host factory into a ``RunMember``: build the member's child host
    (with the SHARED supervisor + its id baked in) and drive it via the unit-043/048
    one-shot ``run_loop`` child, returning the member's final text."""

    async def run_member(
        supervisor: _SwarmSupervisorProto,
        member_id: str,
        instruction: str,
        allowed_tools: tuple[str, ...] | None,
        child_depth: int,
        working_scope: Path,
        fanout: SubagentFanout | None,
    ) -> str:
        def build(
            depth: int,
            allowed: tuple[str, ...] | None,
            scope: Path,
            child_fanout: SubagentFanout | None,
        ) -> LoopPlaneHost:
            return build_member_host(
                supervisor, member_id, depth, allowed, scope, child_fanout
            )

        return await make_run_child(build)(
            instruction, allowed_tools, child_depth, working_scope, fanout
        )

    return run_member


def make_swarm_supervisor(
    task_group: anyio.abc.TaskGroup,
    *,
    build_member_host: MemberHostFactory,
    max_members: int,
    max_messages: int,
) -> SwarmSupervisor:
    """Build a supervisor bound to a scope owner's task group (ADR 0003 D3)."""

    return SwarmSupervisor(
        task_group=task_group,
        run_member=_member_runner(build_member_host),
        max_members=max_members,
        max_messages=max_messages,
    )


def make_swarm_supervisor_factory(
    build_member_host: MemberHostFactory, max_members: int, max_messages: int
) -> Callable[[anyio.abc.TaskGroup], SwarmSupervisor]:
    """Bind the member-host factory + caps into a closure the scope owner calls with its
    own task group, returned to the host assembly so the controller can hold an opaque
    factory and stay tool-agnostic (Constitution V)."""

    def factory(task_group: anyio.abc.TaskGroup) -> SwarmSupervisor:
        return make_swarm_supervisor(
            task_group,
            build_member_host=build_member_host,
            max_members=max_members,
            max_messages=max_messages,
        )

    return factory


_DESCRIPTORS = [
    ToolDescriptor(
        name="swarm_dispatch",
        description=(
            "Dispatch a focused sub-task to a new team member (a bounded child agent "
            "run). Returns a member id immediately (non-blocking); collect the reply "
            "with swarm_get / swarm_list. Pass the work as 'instruction'; optional "
            "allowed_tools restricts the member's tools."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["instruction"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="swarm_get",
        description="Get a team member's status (and reply if completed) by id.",
        input_schema={
            "type": "object",
            "properties": {"member_id": {"type": "string"}},
            "required": ["member_id"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="swarm_list",
        description="List this run's team members with their statuses.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=True,
    ),
    ToolDescriptor(
        name="message_send",
        description=(
            "Send a message to another team member by id (or 'coordinator'). The "
            "recipient reads it with message_inbox."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["to", "content"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="message_inbox",
        description="Read the messages addressed to you (this agent's inbox).",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=True,
    ),
]


def _coerce_allowed_tools(raw: object) -> tuple[str, ...] | None:
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    return None


class SwarmToolsAdapter:
    """A Tool Gateway adapter exposing the five swarm / messaging tools (spec 050).

    Stateless: the per-run state lives in the ``SwarmSupervisor`` reached via
    ``RunContext.swarm``. Holds ``max_subagent_depth`` for the 043 depth cap (a member
    is a child run at ``subagent_depth + 1``).
    """

    def __init__(self, *, max_subagent_depth: int) -> None:
        self._max_subagent_depth = max_subagent_depth

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(_DESCRIPTORS)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        supervisor = context.swarm
        if supervisor is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message="swarm is not enabled for this run",
            )
            return
        self_id = context.swarm_member_id or COORDINATOR
        if name == "swarm_dispatch":
            async for output in self._dispatch(call_input, context, supervisor):
                yield output
            return
        if name == "swarm_list":
            members = supervisor.list_members()
            if not members:
                yield TextBlock(text="no members")
                return
            lines = [f"{m.id}: {m.status}" for m in members]
            yield TextBlock(text="\n".join(lines))
            return
        if name == "message_inbox":
            messages = supervisor.inbox(self_id)
            if not messages:
                yield TextBlock(text="no messages")
                return
            lines = [f"from {m.from_id}: {m.content}" for m in messages]
            yield TextBlock(text="\n".join(lines))
            return
        if name == "message_send":
            to_id = str(call_input["to"])
            content = str(call_input["content"])
            result = supervisor.send(self_id, to_id, content)
            if result == "unknown_recipient":
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"unknown recipient: {to_id}",
                )
                return
            if result == "cap_reached":
                yield ErrorOutput(
                    category=ErrorCategory.POLICY_DENIAL,
                    message="message cap reached; message not sent",
                )
                return
            yield TextBlock(text=f"message sent to {to_id}")
            return
        # swarm_get
        member_id = str(call_input["member_id"])
        member = supervisor.get(member_id)
        if member is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"unknown member id: {member_id}",
            )
            return
        summary = f"member {member_id}: {member.status}"
        if member.reply is not None:
            summary += f"\n{member.reply}"
        yield TextBlock(text=summary)

    async def _dispatch(
        self,
        call_input: dict[str, object],
        context: RunContext,
        supervisor: _SwarmSupervisorProto,
    ) -> AsyncIterator[AdapterOutput]:
        if context.subagent_depth >= self._max_subagent_depth:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message=(
                    f"swarm depth cap reached "
                    f"({self._max_subagent_depth}); refusing to dispatch"
                ),
            )
            return
        instruction = str(call_input["instruction"])
        allowed_tools = _coerce_allowed_tools(call_input.get("allowed_tools"))
        member_id = supervisor.dispatch(
            instruction,
            allowed_tools=allowed_tools,
            child_depth=context.subagent_depth + 1,
            working_scope=context.working_scope,
            fanout=context.subagent_fanout,
        )
        if member_id is None:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message="swarm member cap reached; refusing to dispatch",
            )
            return
        yield TextBlock(text=f"member dispatched: {member_id}")

    async def shutdown(self) -> None:
        return None
