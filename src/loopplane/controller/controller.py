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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
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
from loopplane.budget import BudgetChecker, BudgetPostureSnapshot, UsdBudgetCaps
from loopplane.checkpoint.base import CheckpointStore, SessionSummary
from loopplane.checkpoint.rebuild import rebuild_session
from loopplane.checkpoint.recorder import RecordingSink, SessionRecorder
from loopplane.checkpoint.records import CheckpointRecord
from loopplane.context import (
    BackgroundSupervisor,
    BackgroundSupervisorFactory,
    PlanModeState,
    RunContext,
    ScheduleSupervisor,
    ScheduleSupervisorFactory,
    SwarmSupervisor,
    SwarmSupervisorFactory,
    WorktreeManager,
    WorktreeManagerFactory,
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
from loopplane.fairness import PlatformFairnessGate
from loopplane.gateway.gateway import ToolGateway
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    LifecyclePoint,
    ProcessSetupPayload,
    SessionEndPayload,
    SessionStartPayload,
)
from loopplane.ledger import UsdLedger
from loopplane.loop.assembly import AugmentationProvider, PromptAssembler
from loopplane.loop.compaction import compact_history
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
from loopplane.pricing import PricingTable
from loopplane.skills.advertiser import DEFAULT_PROMPT_BUDGET_CHARS, SkillAdvertiser
from loopplane.skills.loader import LoadedSkill

SessionState = Literal["created", "active", "suspended", "terminated"]
ScopedMemoryProvider = Callable[[str | None], AugmentationProvider | None]
ScopedSkillsProvider = Callable[[str | None], Mapping[str, LoadedSkill]]


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
    model: str | None = None
    starred: bool = False
    forked_from_session_id: str | None = None
    forked_from_sequence: int | None = None
    context_id: str | None = None
    context_name: str | None = None
    context_workspace_label: str | None = None
    context_status: str | None = None
    # Ephemeral 077 display metadata. These fields are deliberately absent from
    # checkpoint records: host rebuilds therefore cannot reconstruct them.
    active_permission_mode: str | None = None
    active_plan_mode: PlanModeState | None = None
    last_accepted_permission_mode: str | None = None


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
        scoped_memory_provider: ScopedMemoryProvider | None = None,
        scoped_skills_provider: ScopedSkillsProvider | None = None,
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
        worktree_manager_factory: WorktreeManagerFactory | None = None,
        max_worktrees: int = 0,
        pricing_table: PricingTable | None = None,
        model_id: str | None = None,
        per_message_usd: Decimal | None = None,
        per_session_usd: Decimal | None = None,
        pre_turn_max_output_tokens: int | None = None,
        usd_ledger: UsdLedger | None = None,
        per_user_monthly_usd: Decimal | None = None,
        platform_fairness: PlatformFairnessGate | None = None,
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
        # Worktree isolation (spec 051): an injected manager factory + count cap, to
        # build a per-session worktree manager from the working scope; off by default
        # (None / 0) → byte-identical. No task group (synchronous git ops). The
        # controller stays tool-agnostic (Constitution V).
        self._worktree_manager_factory = worktree_manager_factory
        self._max_worktrees = max_worktrees
        # USD budget caps (spec 055; G22 Phase B; ADR 0005): the host-supplied 053
        # pricing table + model-id + the per-message/per-session USD caps. All inert by
        # default (None) → no BudgetChecker is built and the loop is byte-identical.
        # When caps + a pricing table + a model-id are ALL present, _assemble builds a
        # per-session BudgetChecker and threads it into the AgentLoop; the session USD
        # total lives on that checker (carried by the per-session loop) and resets on
        # resume() (the session is rebuilt → a fresh checker). pricing/budget are
        # foundational packages (not the tools layer) → the gateway audit is unaffected.
        self._pricing_table = pricing_table
        self._budget_model_id = model_id
        self._per_message_usd = per_message_usd
        self._per_session_usd = per_session_usd
        self._pre_turn_max_output_tokens = pre_turn_max_output_tokens
        # USD per-user-monthly cap (spec 063; G22 Phase C; ADR 0010): a host-supplied
        # durable UsdLedger + the monthly cap. Off by default (None) → byte-identical;
        # when both are set (+ pricing + model-id) _assemble gives the per-session
        # BudgetChecker the monthly dimension, threaded with the run's principal_id on
        # create AND resume. The ledger is a foundational package (not the tools layer).
        self._usd_ledger = usd_ledger
        self._per_user_monthly_usd = per_user_monthly_usd
        self._platform_fairness = platform_fairness
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
        self._scoped_memory_provider = scoped_memory_provider
        self._scoped_skills_provider = scoped_skills_provider
        self._skill_prompt_budget = skill_prompt_budget_chars
        # Assembly is gated (NFR-002): off unless memory or skills are
        # configured, or the host opts in explicitly.
        self._assembly_enabled = (
            enable_assembly
            if enable_assembly is not None
            else (
                memory_store is not None
                or bool(skills)
                or scoped_memory_provider is not None
                or scoped_skills_provider is not None
            )
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
        model: str | None = None,
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
            model=model,
        )
        return session_id

    async def resume(
        self,
        session_id: str,
        *,
        working_scope: Path | None = None,
    ) -> None:
        """Reconstruct conversation state from durable records alone
        (FR-081); repairs and skipped records surface as diagnostics
        (FR-082, FR-083).

        ``working_scope`` is additive and default-preserving (078 T021):
        ``None`` keeps today's ``Path.cwd()`` behaviour exactly.
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
            working_scope=Path.cwd() if working_scope is None else working_scope,
            label=rebuilt.label,
            turn_budget=None,
            created_at=rebuilt.created_at or datetime.now(UTC),
            state="active",
            entries=rebuilt.entries,
            decisions=decisions,
            next_record_sequence=max(record.sequence for record in records) + 1,
            meta_recorded=True,
            principal_id=rebuilt.principal_id,
            model=rebuilt.model,
            starred=rebuilt.starred,
            forked_from_session_id=rebuilt.forked_from_session_id,
            forked_from_sequence=rebuilt.forked_from_sequence,
            context_id=rebuilt.context_id,
            context_name=rebuilt.context_name,
            context_workspace_label=rebuilt.context_workspace_label,
            context_status=rebuilt.context_status,
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
        model: str | None = None,
        starred: bool = False,
        forked_from_session_id: str | None = None,
        forked_from_sequence: int | None = None,
        context_id: str | None = None,
        context_name: str | None = None,
        context_workspace_label: str | None = None,
        context_status: str | None = None,
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
                model=model,
                forked_from_session_id=forked_from_session_id,
                forked_from_sequence=forked_from_sequence,
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
            if self._scoped_memory_provider is not None:
                scoped_memory = self._scoped_memory_provider(principal_id)
                if scoped_memory is not None:
                    providers.append(scoped_memory)
            active_skills = dict(self._skills)
            if self._scoped_skills_provider is not None:
                for name, skill in self._scoped_skills_provider(principal_id).items():
                    active_skills.setdefault(name, skill)
            if active_skills:
                providers.append(
                    SkillAdvertiser(
                        active_skills, prompt_budget_chars=self._skill_prompt_budget
                    )
                )
            assembler = PromptAssembler(
                providers=providers,
                replacement_previews=ledger.previews if ledger is not None else None,
                keep_last=self._assembly_keep_last,
                compact_threshold=self._auto_compact_threshold,
            )

        # USD budget caps (spec 055; ADR 0005): build a per-session checker only when
        # caps + a host-supplied pricing table + a model-id are ALL set; otherwise
        # None → the loop is byte-identical. This is the only place USD accounting is
        # wired; the loop consults the checker per turn and terminates `budget-exceeded`
        # after a crossing turn. The per-session total lives on the checker; because
        # _assemble runs once per session (create + resume), the checker persists across
        # this session's runs and resets on resume (a fresh assembly).
        # 063 (ADR 0010): a checker is also built for a per-user-monthly cap. The
        # monthly dimension (ledger + principal_id + per_user_monthly_usd) is threaded
        # in but only activates inside the checker when all three are set; principal_id
        # is supplied on create AND resume so the monthly cap enforces on resumed
        # sessions too. A cost source (pricing + model-id) is required for any cap.
        budget_checker: BudgetChecker | None = None
        _any_cap = (
            self._per_message_usd is not None
            or self._per_session_usd is not None
            or self._per_user_monthly_usd is not None
        )
        if _any_cap and (
            self._pricing_table is not None and self._budget_model_id is not None
        ):
            budget_checker = BudgetChecker(
                caps=UsdBudgetCaps(
                    per_message_usd=self._per_message_usd,
                    per_session_usd=self._per_session_usd,
                ),
                pricing=self._pricing_table,
                model_id=self._budget_model_id,
                pre_turn_max_output_tokens=self._pre_turn_max_output_tokens,
                ledger=self._usd_ledger,
                principal_id=principal_id,
                per_user_monthly_usd=self._per_user_monthly_usd,
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
                budget_checker=budget_checker,
                platform_fairness=self._platform_fairness,
            ),
            broker=InteractionBroker(emitter=emitter),
            approval_memory={},
            cancellation=anyio.Event(),
            ledger=ledger,
            principal_id=principal_id,
            model=model,
            starred=starred,
            forked_from_session_id=forked_from_session_id,
            forked_from_sequence=forked_from_sequence,
            context_id=context_id,
            context_name=context_name,
            context_workspace_label=context_workspace_label,
            context_status=context_status,
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

    def make_worktree_manager(self, session_id: str) -> WorktreeManager | None:
        """Build a per-session worktree manager from the session's working scope (spec
        051), or ``None`` when worktrees are off. No task group (synchronous git ops);
        the concrete manager comes from the injected factory, so the controller stays
        tool-agnostic (Constitution V)."""

        if self._max_worktrees < 1 or self._worktree_manager_factory is None:
            return None
        return self._worktree_manager_factory(self._require(session_id).working_scope)

    def agent_control_posture(
        self, session_id: str
    ) -> tuple[tuple[str, bool] | None, tuple[str, bool] | None]:
        """Return in-memory 077 display posture, never checkpoint-derived."""

        session = self._sessions.get(session_id)
        if session is None:
            return None, None
        active = (
            (
                session.active_permission_mode,
                bool(session.active_plan_mode and session.active_plan_mode.active),
            )
            if session.active_permission_mode is not None
            else None
        )
        settled = (
            (session.last_accepted_permission_mode, False)
            if session.last_accepted_permission_mode is not None
            else None
        )
        return active, settled

    async def drive(
        self,
        session_id: str,
        input_blocks: Sequence[ContentBlock],
        output_schema: dict[str, object] | None = None,
        permission_mode: str | None = None,
        background_supervisor: BackgroundSupervisor | None = None,
        schedule_supervisor: ScheduleSupervisor | None = None,
        swarm_supervisor: SwarmSupervisor | None = None,
        swarm_member_id: str | None = None,
        worktree_manager: WorktreeManager | None = None,
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
        # A validated browser selection is authoritative only after this point. The
        # active/last values are live controller fields, never recorder input.
        effective_plan_mode = self._plan_mode or permission_mode == "plan"
        plan_mode_state = PlanModeState(active=True) if effective_plan_mode else None
        session.active_permission_mode = permission_mode or "host-default"
        session.active_plan_mode = plan_mode_state
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
            principal_id=session.principal_id,
            cancellation=session.cancellation,
            turn_budget=session.turn_budget,
            session_approval_memory=session.approval_memory,
            subagent_depth=self._subagent_depth,
            interactions=session.broker,
            plan_mode=plan_mode_state,
            permission_mode=permission_mode,
            output_schema=output_schema,
            background_tasks=background_supervisor,
            schedules=schedule_supervisor,
            swarm=swarm_supervisor,
            swarm_member_id=swarm_member_id,
            worktrees=worktree_manager,
        )
        try:
            if self._platform_fairness is None or session.principal_id is None:
                await session.loop.run(input_blocks, context)
            else:
                async with self._platform_fairness.admit(session.principal_id):
                    await session.loop.run(input_blocks, context)
        finally:
            if session.active_permission_mode is not None:
                session.last_accepted_permission_mode = session.active_permission_mode
            session.active_permission_mode = None
            session.active_plan_mode = None
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
                model=session.model,
                starred=session.starred,
                forked_from_session_id=session.forked_from_session_id,
                forked_from_sequence=session.forked_from_sequence,
                context_id=session.context_id,
                context_name=session.context_name,
                context_workspace_label=session.context_workspace_label,
                context_status=session.context_status,
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

    async def set_session_starred(self, session_id: str, starred: bool) -> None:
        """Persist a session's starred flag and update any loaded session."""
        if self._checkpoint is not None:
            await self._checkpoint.update_session_metadata(session_id, starred=starred)
        session = self._sessions.get(session_id)
        if session is not None:
            session.starred = starred

    async def set_session_context(
        self,
        session_id: str,
        *,
        principal_id: str | None,
        context_id: str,
        context_name: str,
        context_workspace_label: str | None,
        context_status: str,
    ) -> None:
        """Persist context metadata only when the requesting principal owns
        the session."""
        summary = next(
            (item for item in self.list_sessions() if item.session_id == session_id),
            None,
        )
        session = self._sessions.get(session_id)
        if summary is not None:
            if summary.principal_id != principal_id:
                raise KeyError(f"unknown session: {session_id}")
        elif session is None or session.principal_id != principal_id:
            raise KeyError(f"unknown session: {session_id}")
        elif self._checkpoint is not None:
            await self._checkpoint.create_session_metadata(
                session_id,
                created_at=session.created_at,
                label=session.label,
                principal_id=session.principal_id,
                model=session.model,
            )

        if self._checkpoint is not None:
            await self._checkpoint.update_session_metadata(
                session_id,
                context_id=context_id,
                context_name=context_name,
                context_workspace_label=context_workspace_label,
                context_status=context_status,
            )
        if session is not None:
            session.context_id = context_id
            session.context_name = context_name
            session.context_workspace_label = context_workspace_label
            session.context_status = context_status

    async def fork_session(
        self,
        source_session_id: str,
        *,
        principal_id: str | None,
        source_sequence: int,
        title: str | None = None,
        model: str | None = None,
    ) -> str:
        """Create an owned fork summary from an existing session point."""
        source = next(
            (
                summary
                for summary in self.list_sessions()
                if summary.session_id == source_session_id
            ),
            None,
        )
        if source is None or source.principal_id != principal_id:
            raise KeyError(f"unknown session: {source_session_id}")
        session_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        label = title if title is not None else source.label
        if self._checkpoint is not None:
            await self._checkpoint.create_session_metadata(
                session_id,
                created_at=now,
                label=label,
                principal_id=principal_id,
                model=model if model is not None else source.model,
                forked_from_session_id=source_session_id,
                forked_from_sequence=source_sequence,
            )
        self._sessions[session_id] = self._assemble(
            session_id=session_id,
            working_scope=Path.cwd(),
            label=label,
            turn_budget=None,
            created_at=now,
            state="created",
            entries=None,
            decisions=(),
            next_record_sequence=2 if self._checkpoint is not None else 1,
            meta_recorded=self._checkpoint is not None,
            principal_id=principal_id,
            model=model if model is not None else source.model,
            forked_from_session_id=source_session_id,
            forked_from_sequence=source_sequence,
        )
        return session_id

    def search_sessions(
        self, query: str, principal_id: str | None
    ) -> list[SessionSummary]:
        """Search owned session labels and retained text content."""
        needle = query.strip().lower()
        if not needle:
            return [
                summary
                for summary in self.list_sessions()
                if summary.principal_id == principal_id
            ]
        matches: list[SessionSummary] = []
        for summary in self.list_sessions():
            if summary.principal_id != principal_id:
                continue
            snippet = self._summary_search_snippet(summary, needle)
            if snippet is None:
                snippet = self._history_search_snippet(summary.session_id, needle)
            if snippet is not None:
                matches.append(replace(summary, search_snippet=snippet))
        return matches

    def bulk_delete_sessions(
        self, session_ids: Sequence[str], *, principal_id: str | None
    ) -> list[str]:
        """Delete the subset of supplied sessions owned by ``principal_id``."""
        owned = {
            summary.session_id
            for summary in self.list_sessions()
            if summary.principal_id == principal_id
        }
        deleted: list[str] = []
        for session_id in session_ids:
            if session_id not in owned or session_id in deleted:
                continue
            self.delete_session(session_id)
            deleted.append(session_id)
        return deleted

    def delete_session(self, session_id: str) -> None:
        """Delete a session (030): drop its durable records and owned artifacts."""
        artifact_deletion = (
            self._artifacts.prepare_session_deletion(session_id)
            if self._artifacts is not None
            else None
        )
        try:
            if self._checkpoint is not None:
                self._checkpoint.delete_session(session_id)
        except Exception:
            records: list[CheckpointRecord] = []
            try:
                if self._checkpoint is not None:
                    records, _problems = self._checkpoint.load(session_id)
            except Exception:
                # The effect cannot be disproved. Keep every other authority in
                # the deleted state rather than restoring dangling references.
                pass
            if records:
                if self._artifacts is not None and artifact_deletion is not None:
                    self._artifacts.rollback_session_deletion(artifact_deletion)
                raise
        if self._artifacts is not None and artifact_deletion is not None:
            self._artifacts.commit_session_deletion(artifact_deletion)
        self._sessions.pop(session_id, None)

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

    def _summary_search_snippet(
        self, summary: SessionSummary, needle: str
    ) -> str | None:
        for candidate in (summary.label, summary.model):
            if candidate is not None and needle in candidate.lower():
                return candidate
        return None

    def _history_search_snippet(self, session_id: str, needle: str) -> str | None:
        entries = self._entries_for_search(session_id)
        for entry in entries:
            for block in entry.blocks:
                if isinstance(block, TextBlock) and needle in block.text.lower():
                    return block.text[:240]
        return None

    def _entries_for_search(self, session_id: str) -> tuple[HistoryEntry, ...]:
        session = self._sessions.get(session_id)
        if session is not None:
            return session.history.snapshot()
        if self._checkpoint is None:
            return ()
        records, _ = self._checkpoint.load(session_id)
        if not records:
            return ()
        return tuple(rebuild_session(records).entries)

    def session_cost(self, session_id: str) -> Decimal | None:
        """The session's accumulated USD, or ``None`` when no budget checker is
        configured (064 cost surfacing; read-only). Raises for an unknown session."""
        return self._require(session_id).loop.current_session_cost()

    def budget_posture(self, session_id: str) -> BudgetPostureSnapshot:
        """Return live enum-only diagnostics, never checkpoint-derived."""
        session = self._sessions.get(session_id)
        if session is None:
            return BudgetPostureSnapshot()
        return session.loop.current_budget_posture()

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        """A principal's current-month accumulated USD from the durable ledger, or
        ``None`` when no ledger is configured (064 cost surfacing; read-only). The
        month is the UTC ``YYYY-MM`` derivation consistent with 063's enforcement."""
        if self._usd_ledger is None:
            return None
        return self._usd_ledger.get(principal_id, datetime.now(UTC).strftime("%Y-%m"))

    def compact_session(self, session_id: str) -> bool:
        """Compact a session's history via the EXISTING ``compact_history`` (the
        loop's compaction seam) with this controller's ``keep_last`` (065 ``/compact``;
        no new compaction path). Returns whether anything was compacted. Raises for an
        unknown session."""
        history = self._require(session_id).history
        return compact_history(history, keep_last=self._assembly_keep_last)

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
