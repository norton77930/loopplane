"""The Runtime Controller: session lifecycle — create, attach, drive,
detach, resume, terminate, list (contracts/run-lifecycle.md; FR-010).

The Controller owns the recording boundary (FR-094): when a checkpoint
store is configured, history appends and run terminations are recorded
durably as they occur, and replacement decisions flow through the same
stream. Without stores, sessions are purely in-memory (the US1/US2 posture).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anyio

from loopplane.approval.interactions import InteractionBroker
from loopplane.artifacts.budget import (
    DEFAULT_REPLACEMENT_BUDGET_BYTES,
    ReplacementDecision,
    ReplacementLedger,
)
from loopplane.artifacts.store import ArtifactStore
from loopplane.checkpoint.base import CheckpointStore, SessionSummary
from loopplane.checkpoint.rebuild import rebuild_session
from loopplane.checkpoint.recorder import RecordingSink, SessionRecorder
from loopplane.context import (
    BackgroundSupervisor,
    BackgroundSupervisorFactory,
    PlanModeState,
    RunContext,
    ScheduleSupervisor,
    ScheduleSupervisorFactory,
    SwarmSupervisor,
    SwarmSupervisorFactory,
)
from loopplane.events.emitter import EventEmitter, EventSink
from loopplane.events.envelope import (
    AssistantOutputIncrementEvent,
    AssistantOutputIncrementPayload,
    ReplayCompletedEvent,
    ReplayCompletedPayload,
    ReplayStartedEvent,
    ReplayStartedPayload,
    RuntimeEvent,
    ToolCallCompletedEvent,
    ToolCallCompletedPayload,
    ToolCallStartedEvent,
    ToolCallStartedPayload,
    UserInputEvent,
    UserInputPayload,
)
from loopplane.events.sequencer import EventSequencer
from loopplane.gateway.gateway import ToolGateway
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    LifecyclePoint,
    ProcessSetupPayload,
    SessionEndPayload,
    SessionStartPayload,
)
from loopplane.loop.assembly import AugmentationProvider, PromptAssembler
from loopplane.loop.history import (
    HistoryEntry,
    HistoryHook,
    SessionHistory,
    is_tool_results_entry,
)
from loopplane.loop.loop import AgentLoop
from loopplane.memory.provider import MemoryAugmentation
from loopplane.memory.store import MemoryStore
from loopplane.model.boundary import ModelBoundary
from loopplane.model.content import (
    ContentBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)
from loopplane.skills.advertiser import DEFAULT_PROMPT_BUDGET_CHARS, SkillAdvertiser
from loopplane.skills.loader import LoadedSkill

SessionState = Literal["created", "active", "suspended", "terminated"]


@dataclass
class _Session:
    session_id: str
    working_scope: Path
    label: str | None
    created_at: datetime
    last_active_at: datetime
    state: SessionState
    turn_budget: int | None
    history: SessionHistory
    emitter: EventEmitter
    sink: EventSink
    sequencer: EventSequencer
    loop: AgentLoop
    broker: InteractionBroker
    approval_memory: dict[str, Literal["allow", "deny"]]
    cancellation: anyio.Event
    ledger: ReplacementLedger | None = None
    attached: bool = False
    driving: bool = False
    started: bool = False
    principal_id: str | None = None


class RuntimeController:
    def __init__(
        self,
        *,
        model: ModelBoundary,
        gateway: ToolGateway,
        event_sink: EventSink,
        checkpoint_store: CheckpointStore | None = None,
        artifact_store: ArtifactStore | None = None,
        replacement_budget_bytes: int = DEFAULT_REPLACEMENT_BUDGET_BYTES,
        memory_store: MemoryStore | None = None,
        skills: Mapping[str, LoadedSkill] | None = None,
        skill_prompt_budget_chars: int = DEFAULT_PROMPT_BUDGET_CHARS,
        enable_assembly: bool | None = None,
        assembly_keep_last: int = 4,
        auto_compact_threshold: float | None = None,
        compaction_summarizer: ModelBoundary | None = None,
        hooks: HookDispatcher | None = None,
        plan_mode: bool = False,
        subagent_depth: int = 0,
        background_supervisor_factory: BackgroundSupervisorFactory | None = None,
        max_background_tasks: int = 0,
        schedule_supervisor_factory: ScheduleSupervisorFactory | None = None,
        max_schedules: int = 0,
        swarm_supervisor_factory: SwarmSupervisorFactory | None = None,
        max_swarm_members: int = 0,
    ) -> None:
        self._model = model
        self._gateway = gateway
        self._event_sink = event_sink
        # Whether runs start in plan mode (spec 038); off by default. The per-run
        # holder is created in drive() — the single place RunContext is constructed.
        self._plan_mode = plan_mode
        # This controller's subagent recursion depth (spec 043); 0 for a top-level
        # run. A child controller built to run a spawned subagent is given depth+1,
        # stamped onto each run's RunContext in drive(). Default 0 → unchanged.
        self._subagent_depth = subagent_depth
        # Background tasks (spec 048; ADR 0002): an injected supervisor factory (built
        # by the host assembly, which owns the tools-layer import) + the count cap, to
        # build a per-run supervisor on demand; both off by default (None / 0) →
        # byte-identical. The controller stays tool-agnostic (Constitution V).
        self._background_supervisor_factory = background_supervisor_factory
        self._max_background_tasks = max_background_tasks
        # Agent scheduling (spec 049): an injected supervisor factory + count cap, used
        # to build a per-run schedule supervisor on demand; off by default (None / 0) →
        # byte-identical. The controller stays tool-agnostic (Constitution V).
        self._schedule_supervisor_factory = schedule_supervisor_factory
        self._max_schedules = max_schedules
        # Agent messaging & swarm (spec 050; ADR 0003): an injected supervisor factory +
        # cap to build a per-run swarm supervisor on demand; off by default (None / 0) →
        # byte-identical. The controller stays tool-agnostic (Constitution V).
        self._swarm_supervisor_factory = swarm_supervisor_factory
        self._max_swarm_members = max_swarm_members
        # Optional lifecycle hooks (feature 015); absent by default (FR-011).
        # process_setup fires at most once per controller lifetime.
        self._hooks = hooks
        self._setup_fired = False
        self._background: set[asyncio.Task[None]] = set()
        self._checkpoint = checkpoint_store
        self._artifacts = artifact_store
        self._replacement_budget = replacement_budget_bytes
        self._memory_store = memory_store
        self._skills = dict(skills) if skills else {}
        self._skill_prompt_budget = skill_prompt_budget_chars
        # Assembly is gated (NFR-002): off unless memory or skills are
        # configured, or the host opts in explicitly.
        self._assembly_enabled = (
            enable_assembly
            if enable_assembly is not None
            else (memory_store is not None or bool(skills))
        )
        self._assembly_keep_last = assembly_keep_last
        # Proactive auto-compaction threshold (spec 041): None → the assembler's
        # existing full-capacity proactive check (default-off, byte-identical); a
        # fraction in (0, 1] → compact proactively at that fraction of capacity.
        self._auto_compact_threshold = auto_compact_threshold
        # Optional cheap-model compaction summarizer (spec 042): None → the
        # mechanical digest (default, byte-identical). A ModelBoundary → the loop's
        # FAIL-SAFE overlay summarizes the dropped span into the summary marker.
        self._compaction_summarizer = compaction_summarizer
        self._sessions: dict[str, _Session] = {}

    def create_session(
        self,
        *,
        working_scope: Path,
        label: str | None = None,
        turn_budget: int | None = None,
        principal_id: str | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        self._sessions[session_id] = self._assemble(
            session_id=session_id,
            working_scope=working_scope,
            label=label,
            turn_budget=turn_budget,
            created_at=now,
            state="created",
            entries=None,
            decisions=(),
            next_record_sequence=1,
            meta_recorded=False,
            principal_id=principal_id,
        )
        return session_id

    async def resume(self, session_id: str) -> None:
        """Reconstruct conversation state from durable records alone
        (FR-081); repairs and skipped records surface as diagnostics
        (FR-082, FR-083).
        """
        if self._checkpoint is None:
            raise RuntimeError("resume requires a checkpoint store")
        records, problems = self._checkpoint.load(session_id)
        if not records:
            raise KeyError(f"unknown session: {session_id}")
        rebuilt = rebuild_session(records)
        decisions = tuple(
            ReplacementDecision(
                artifact_reference=payload.artifact_reference,
                replaced_call_id=payload.replaced_call_id,
                preview=payload.preview,
                decided_at=payload.decided_at,
            )
            for payload in rebuilt.decisions
        )
        session = self._assemble(
            session_id=session_id,
            working_scope=Path.cwd(),
            label=rebuilt.label,
            turn_budget=None,
            created_at=rebuilt.created_at or datetime.now(UTC),
            state="active",
            entries=rebuilt.entries,
            decisions=decisions,
            next_record_sequence=max(record.sequence for record in records) + 1,
            meta_recorded=True,
        )
        self._sessions[session_id] = session
        for problem in problems:
            await session.emitter.diagnostic("warning", "checkpoint", problem)
        for repair in rebuilt.repairs:
            await session.emitter.diagnostic("warning", "checkpoint", repair)

    def _assemble(
        self,
        *,
        session_id: str,
        working_scope: Path,
        label: str | None,
        turn_budget: int | None,
        created_at: datetime,
        state: SessionState,
        entries: Sequence[HistoryEntry] | None,
        decisions: Sequence[ReplacementDecision],
        next_record_sequence: int,
        meta_recorded: bool,
        principal_id: str | None = None,
    ) -> _Session:
        ledger: ReplacementLedger | None = None
        if self._artifacts is not None:
            ledger = ReplacementLedger(
                budget_bytes=self._replacement_budget,
                store=self._artifacts,
                session_id=session_id,
            )
            ledger.restore(decisions)

        sink: EventSink = self._event_sink
        hook: HistoryHook | None = None
        if self._checkpoint is not None:
            recorder = SessionRecorder(
                store=self._checkpoint,
                session_id=session_id,
                created_at=created_at,
                label=label,
                principal_id=principal_id,
                next_sequence=next_record_sequence,
                meta_recorded=meta_recorded,
            )
            sink = RecordingSink(self._event_sink, recorder)
            hook = self._make_history_hook(recorder, ledger)

        assembler: PromptAssembler | None = None
        if self._assembly_enabled:
            providers: list[AugmentationProvider] = []
            if self._memory_store is not None:
                providers.append(MemoryAugmentation(self._memory_store))
            if self._skills:
                providers.append(
                    SkillAdvertiser(
                        self._skills, prompt_budget_chars=self._skill_prompt_budget
                    )
                )
            assembler = PromptAssembler(
                providers=providers,
                replacement_previews=ledger.previews if ledger is not None else None,
                keep_last=self._assembly_keep_last,
                compact_threshold=self._auto_compact_threshold,
            )

        sequencer = EventSequencer()
        emitter = EventEmitter(session_id=session_id, sequencer=sequencer, sink=sink)
        history = SessionHistory(on_append=hook)
        if entries is not None:
            history.restore(entries)
        return _Session(
            session_id=session_id,
            working_scope=working_scope,
            label=label,
            created_at=created_at,
            last_active_at=datetime.now(UTC),
            state=state,
            turn_budget=turn_budget,
            history=history,
            emitter=emitter,
            sink=sink,
            sequencer=sequencer,
            loop=AgentLoop(
                model=self._model,
                gateway=self._gateway,
                emitter=emitter,
                history=history,
                assembler=assembler,
                hooks=self._hooks,
                summarizer=self._compaction_summarizer,
            ),
            broker=InteractionBroker(emitter=emitter),
            approval_memory={},
            cancellation=anyio.Event(),
            ledger=ledger,
            principal_id=principal_id,
        )

    def _make_history_hook(
        self, recorder: SessionRecorder, ledger: ReplacementLedger | None
    ) -> HistoryHook:
        async def hook(entry: HistoryEntry) -> None:
            await recorder.record_entry(entry)
            if ledger is None or not is_tool_results_entry(entry):
                return
            for block in entry.blocks:
                if not isinstance(block, ToolResultBlock):
                    continue
                for decision in await ledger.track(block.call_id, list(block.outputs)):
                    await recorder.record_replacement(
                        artifact_reference=decision.artifact_reference,
                        replaced_call_id=decision.replaced_call_id,
                        preview=decision.preview,
                        decided_at=decision.decided_at,
                    )

        return hook

    @property
    def max_background_tasks(self) -> int:
        return self._max_background_tasks

    def make_background_supervisor(
        self, task_group: anyio.abc.TaskGroup
    ) -> BackgroundSupervisor | None:
        """Build a per-run background-task supervisor bound to ``task_group`` (spec 048;
        ADR 0002), or ``None`` when background tasks are disabled. The scope owner (the
        Dispatcher / the one-shot ``host.run``) calls this with a task group it owns and
        passes the result to ``drive``. The concrete supervisor comes from the injected
        factory (the host assembly owns the tools-layer import), so the controller stays
        tool-agnostic (Constitution V)."""

        if (
            self._max_background_tasks < 1
            or self._background_supervisor_factory is None
        ):
            return None
        return self._background_supervisor_factory(task_group)

    @property
    def max_schedules(self) -> int:
        return self._max_schedules

    def make_schedule_supervisor(
        self, task_group: anyio.abc.TaskGroup
    ) -> ScheduleSupervisor | None:
        """Build a per-run schedule supervisor bound to ``task_group`` (spec 049), or
        ``None`` when scheduling is disabled. The scope owner (the Dispatcher / the
        one-shot ``host.run``) calls this with a task group it owns and passes the
        result to ``drive``; the concrete supervisor comes from the injected factory,
        so the controller stays tool-agnostic (Constitution V)."""

        if self._max_schedules < 1 or self._schedule_supervisor_factory is None:
            return None
        return self._schedule_supervisor_factory(task_group)

    @property
    def max_swarm_members(self) -> int:
        return self._max_swarm_members

    def make_swarm_supervisor(
        self, task_group: anyio.abc.TaskGroup
    ) -> SwarmSupervisor | None:
        """Build a per-run swarm supervisor bound to ``task_group`` (spec 050), or
        ``None`` when swarm is off. The scope owner (the Dispatcher / one-shot
        ``host.run``) calls this with a task group it owns and passes the result to
        ``drive``; the concrete supervisor comes from the injected factory, so the
        controller stays tool-agnostic (Constitution V)."""

        if self._max_swarm_members < 1 or self._swarm_supervisor_factory is None:
            return None
        return self._swarm_supervisor_factory(task_group)

    async def drive(
        self,
        session_id: str,
        input_blocks: Sequence[ContentBlock],
        output_schema: dict[str, object] | None = None,
        background_supervisor: BackgroundSupervisor | None = None,
        schedule_supervisor: ScheduleSupervisor | None = None,
        swarm_supervisor: SwarmSupervisor | None = None,
        swarm_member_id: str | None = None,
    ) -> None:
        """Run one complete turn cycle; ends with exactly one run-terminated
        event (FR-001).

        ``output_schema`` is an optional per-run JSON schema for structured output
        (spec 045); ``None`` (the default) is byte-identical to pre-045. It is
        stamped onto the run's ``RunContext`` and forwarded to the assembled
        ``ModelRequest``.
        """
        session = self._require(session_id)
        if session.state == "terminated":
            raise RuntimeError(f"session is terminated: {session_id}")
        if session.driving:
            raise RuntimeError(f"a run is already active for session: {session_id}")
        session.driving = True
        session.state = "active"
        if self._hooks is not None:
            if not self._setup_fired:
                self._setup_fired = True
                await self._hooks.fire(
                    LifecyclePoint.process_setup, ProcessSetupPayload()
                )
            if not session.started:
                session.started = True
                await self._hooks.fire(
                    LifecyclePoint.session_start,
                    SessionStartPayload(
                        session_id=session.session_id, label=session.label
                    ),
                )
        context = RunContext(
            session_id=session_id,
            working_scope=session.working_scope,
            cancellation=session.cancellation,
            turn_budget=session.turn_budget,
            session_approval_memory=session.approval_memory,
            subagent_depth=self._subagent_depth,
            interactions=session.broker,
            plan_mode=PlanModeState(active=True) if self._plan_mode else None,
            output_schema=output_schema,
            background_tasks=background_supervisor,
            schedules=schedule_supervisor,
            swarm=swarm_supervisor,
            swarm_member_id=swarm_member_id,
        )
        try:
            await session.loop.run(input_blocks, context)
        finally:
            session.driving = False
            session.last_active_at = datetime.now(UTC)
            # The signal is one-shot; arm a fresh one for the next run.
            session.cancellation = anyio.Event()

    async def attach(self, session_id: str) -> None:
        """Bind the single driving consumer (research A8), replacing any
        previous attachment; durable history replays first as events with
        `replay: true`, bracketed by replay-started/-completed (FR-014).
        """
        session = self._require(session_id)
        session.attached = True
        # Allocate the bracket's opening sequence before the body so emitted
        # sequences stay monotonic in delivery order (FR-015 / envelope).
        started_sequence = session.sequencer.next_sequence()
        body = self._replay_events(session)
        completed_sequence = session.sequencer.next_sequence()
        await session.sink(
            ReplayStartedEvent(
                session_id=session_id,
                sequence=started_sequence,
                occurred_at=datetime.now(UTC),
                replay=True,
                payload=ReplayStartedPayload(count=len(body)),
            )
        )
        for event in body:
            await session.sink(event)
        await session.sink(
            ReplayCompletedEvent(
                session_id=session_id,
                sequence=completed_sequence,
                occurred_at=datetime.now(UTC),
                replay=True,
                payload=ReplayCompletedPayload(count=len(body)),
            )
        )

    def _replay_events(self, session: _Session) -> list[RuntimeEvent]:
        """History as events, sufficient to reconstruct the visible
        conversation (FR-014).
        """
        now = datetime.now(UTC)
        results_by_call: dict[str, ToolResultBlock] = {}
        for entry in session.history.snapshot():
            for block in entry.blocks:
                if isinstance(block, ToolResultBlock):
                    results_by_call[block.call_id] = block

        events: list[RuntimeEvent] = []

        def sequence() -> int:
            return session.sequencer.next_sequence()

        turn_index = 0
        for entry in session.history.snapshot():
            blocks = entry.blocks
            if entry.role == "user":
                if blocks and all(isinstance(b, ToolResultBlock) for b in blocks):
                    continue  # results replay with their calls below
                events.append(
                    UserInputEvent(
                        session_id=session.session_id,
                        sequence=sequence(),
                        occurred_at=now,
                        replay=True,
                        payload=UserInputPayload(blocks=list(blocks)),
                    )
                )
                continue
            text = "".join(b.text for b in blocks if isinstance(b, TextBlock))
            if text:
                events.append(
                    AssistantOutputIncrementEvent(
                        session_id=session.session_id,
                        sequence=sequence(),
                        occurred_at=now,
                        replay=True,
                        payload=AssistantOutputIncrementPayload(
                            text=text, turn_index=turn_index
                        ),
                    )
                )
            for block in blocks:
                if not isinstance(block, ToolCallBlock):
                    continue
                events.append(
                    ToolCallStartedEvent(
                        session_id=session.session_id,
                        sequence=sequence(),
                        occurred_at=now,
                        replay=True,
                        payload=ToolCallStartedPayload(
                            call_id=block.call_id,
                            tool_name=block.tool_name,
                            input=block.input,
                        ),
                    )
                )
                result = results_by_call.get(block.call_id)
                if result is None:
                    continue
                events.append(
                    ToolCallCompletedEvent(
                        session_id=session.session_id,
                        sequence=sequence(),
                        occurred_at=now,
                        replay=True,
                        payload=ToolCallCompletedPayload(
                            call_id=result.call_id,
                            outcome=result.outcome,
                            outputs=result.outputs,
                            artifact_reference=result.artifact_reference,
                            error=result.error,
                            duration_seconds=0.0,
                        ),
                    )
                )
            turn_index += 1
        return events

    def detach(self, session_id: str) -> None:
        """Unbind the consumer: in-flight work cancels cleanly and the
        session suspends, consistent and resumable.
        """
        session = self._require(session_id)
        session.attached = False
        session.cancellation.set()
        if session.state != "terminated":
            session.state = "suspended"
            self._fire_session_end(session, "suspended")

    def list_sessions(self) -> list[SessionSummary]:
        """Identity and recency, newest first (FR-085)."""
        if self._checkpoint is not None:
            return self._checkpoint.list_sessions()
        summaries = [
            SessionSummary(
                session_id=session.session_id,
                label=session.label,
                created_at=session.created_at,
                last_active_at=session.last_active_at,
                principal_id=session.principal_id,
            )
            for session in self._sessions.values()
        ]
        return sorted(summaries, key=lambda s: s.last_active_at, reverse=True)

    async def set_session_title(self, session_id: str, title: str) -> None:
        """Persist a new title (030): append a fresh session-meta when a
        checkpoint store is configured, and update a loaded session's label."""
        if self._checkpoint is not None:
            await self._checkpoint.set_title(session_id, title)
        session = self._sessions.get(session_id)
        if session is not None:
            session.label = title

    def delete_session(self, session_id: str) -> None:
        """Delete a session (030): drop the in-memory session and durably
        remove its records when a checkpoint store is configured."""
        self._sessions.pop(session_id, None)
        if self._checkpoint is not None:
            self._checkpoint.delete_session(session_id)

    def cancel(self, session_id: str) -> None:
        """Request cancellation: takes effect pre-turn and mid-stream and
        never raises to the caller (FR-003).
        """
        self._require(session_id).cancellation.set()

    def history_snapshot(self, session_id: str) -> tuple[HistoryEntry, ...]:
        """A point-in-time history snapshot that cannot mutate internal
        state (FR-006).
        """
        return self._require(session_id).history.snapshot()

    def terminate(self, session_id: str) -> None:
        session = self._require(session_id)
        session.cancellation.set()
        session.state = "terminated"
        self._fire_session_end(session, "terminated")

    def _fire_session_end(self, session: _Session, state: str) -> None:
        # session_end is observational (feature 015). terminate/detach are part
        # of the synchronous public surface, so the end hooks fire-and-forget on
        # the running loop; a retained task reference avoids premature GC.
        if self._hooks is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(
            self._hooks.fire(
                LifecyclePoint.session_end,
                SessionEndPayload(session_id=session.session_id, state=state),
            )
        )
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def emit_diagnostic(
        self,
        session_id: str,
        severity: Literal["info", "warning", "error"],
        category: str,
        message: str,
    ) -> None:
        await self._require(session_id).emitter.diagnostic(severity, category, message)

    def attach_reviewer(self, session_id: str) -> None:
        self._require(session_id).broker.attach_reviewer()

    def on_reviewer_disconnect(self, session_id: str) -> None:
        """Disconnect semantics (FR-013, FR-115): every pending approval
        denies, every pending question cancels.
        """
        self._require(session_id).broker.on_disconnect()

    def resolve_approval(
        self,
        session_id: str,
        request_id: str,
        *,
        decision: Literal["allow", "deny"],
        scope: Literal["once", "session"],
        reason: str | None = None,
    ) -> bool:
        return self._require(session_id).broker.resolve_approval(
            request_id, decision=decision, scope=scope, reason=reason
        )

    def answer_question(
        self, session_id: str, request_id: str, answers: Sequence[str]
    ) -> bool:
        return self._require(session_id).broker.answer_question(request_id, answers)

    def _require(self, session_id: str) -> _Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        return session
