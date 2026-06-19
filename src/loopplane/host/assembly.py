"""The Reference Runner: maps a :class:`RuntimeConfig` onto wired Phase-1
components (spec FR-020–FR-024).

This is the single assembly path. ``LoopPlaneHost`` and the example runner both
go through :func:`assemble`, so smoke tests exercise the real embedding path and
there is never a second, divergent wiring (FR-024). It composes Phase-1
components only through their declared interfaces and re-implements none of them
(FR-060).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loopplane.approval import HumanApproval, PermissionRule
from loopplane.artifacts import ArtifactStore, make_artifact_handoff
from loopplane.checkpoint import (
    CheckpointStore,
    FileCheckpointStore,
    SqliteCheckpointStore,
)
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import PolicyDecider, ToolGateway
from loopplane.governance import (
    all_of,
    network_policy,
    plan_mode_policy,
    rule_dsl_policy,
    safe_failure,
)
from loopplane.host.config import (
    RuntimeConfig,
    approval_effects,
    collect_tool_names,
    validate_config,
)
from loopplane.host.sink import RunSink
from loopplane.memory import MemoryStore
from loopplane.observability import maybe_attach
from loopplane.skills import SkillToolAdapter, load_skills, skill_profiles
from loopplane.skills.loader import LoadedSkill

if TYPE_CHECKING:
    from loopplane.host.host import LoopPlaneHost
    from loopplane.tools.subagent import ChildHostFactory


async def _noop_sink(event: RuntimeEvent) -> None:
    """A do-nothing inner sink for the observability overlay: the overlay records
    telemetry and forwards here, while real delivery happens through RunSink."""
    return None


@dataclass
class AssembledRuntime:
    """The wired runtime the facade owns: the controller plus the host-side
    handles it needs (the rebindable sink, stores for inspection)."""

    controller: RuntimeController
    sink: RunSink
    artifact_store: ArtifactStore | None
    checkpoint_store: CheckpointStore | None
    skill_problems: tuple[str, ...]
    # Read-only refs retained for inspection (027); already built below; additive.
    gateway: ToolGateway
    skills: Mapping[str, LoadedSkill]
    memory_store: MemoryStore | None


def assemble(config: RuntimeConfig, *, subagent_depth: int = 0) -> AssembledRuntime:
    """Validate and wire a runtime from a configuration (FR-020, FR-005).

    ``subagent_depth`` (spec 043) is this runtime's recursion depth, stamped onto each
    run's ``RunContext`` by the controller; ``0`` for a top-level host. A child host
    built to run a spawned subagent is assembled at ``parent + 1`` so its own
    ``spawn_subagent`` is capped one level deeper. Default ``0`` → unchanged.
    """

    validate_config(config)

    # Durable backends — both or neither, wired together (FR-002).
    artifact_store: ArtifactStore | None = None
    checkpoint_store: CheckpointStore | None = None
    artifact_handoff = None
    output_limit_bytes: int | None = None
    replacement_budget_bytes: int | None = None
    if config.storage is not None:
        artifact_store = ArtifactStore(config.storage.root)
        if config.storage.checkpoint_backend == "sqlite":
            checkpoint_store = SqliteCheckpointStore(
                config.storage.root / "checkpoints.sqlite3"
            )
        else:
            checkpoint_store = FileCheckpointStore(config.storage.root)
        artifact_handoff = make_artifact_handoff(artifact_store)
        output_limit_bytes = config.storage.artifact_threshold_bytes
        replacement_budget_bytes = config.storage.replacement_budget_bytes

    # Optional skills (off by default; FR-012).
    skills_map = None
    skill_problems: tuple[str, ...] = ()
    skill_adapter: SkillToolAdapter | None = None
    if config.skills is not None:
        skills_map, problems = load_skills(list(config.skills.sources))
        skill_problems = tuple(str(problem) for problem in problems)
        skill_adapter = SkillToolAdapter(skills_map)

    memory_store = (
        MemoryStore(config.memory.source) if config.memory is not None else None
    )

    # All tool names must be known before the gateway is built so the policy
    # decider can be constructed with its rules (the gateway takes ``decide`` at
    # construction).
    tool_names = collect_tool_names(config)
    if skill_adapter is not None:
        tool_names.extend(descriptor.name for descriptor in skill_adapter.describe())
    decide = _build_decider(config, tool_names, skills_map)

    gateway_kwargs: dict[str, Any] = {}
    if decide is not None:
        gateway_kwargs["decide"] = decide
    if artifact_handoff is not None:
        gateway_kwargs["artifact_handoff"] = artifact_handoff
    if output_limit_bytes is not None:
        gateway_kwargs["output_limit_bytes"] = output_limit_bytes
    gateway = ToolGateway(**gateway_kwargs)
    for spec in config.tools:
        gateway.register(spec.descriptor, spec.handler)
    for adapter in config.tool_adapters:
        gateway.register_adapter(adapter)
    if skill_adapter is not None:
        gateway.register_adapter(skill_adapter)
    # Opt-in model-driven subagent spawning (spec 043): register the spawn tool only
    # when a non-zero recursion cap is configured (cap 0 → no tool, byte-identical to
    # today). The child host is built lazily, at parent depth + 1, from this config.
    # Imported lazily here (not at module scope) to avoid an import cycle:
    # engineering → host → assembly → tools.subagent → engineering.
    if config.max_subagent_depth >= 1:
        from loopplane.tools.subagent import SpawnSubagentAdapter

        gateway.register_adapter(
            SpawnSubagentAdapter(
                build_child_host=_make_child_host_builder(config),
                max_subagent_depth=config.max_subagent_depth,
            )
        )
    # Opt-in background tasks (spec 048; ADR 0002): register the five background-task
    # tools only when a non-zero count cap is set (0 → no tools, byte-identical). The
    # supervisor is built per-run by the scope owner (Dispatcher / host.run) from the
    # controller; the tools read it via RunContext.background_tasks. Lazy import.
    if config.max_background_tasks >= 1:
        from loopplane.tools.background import BackgroundTasksAdapter

        gateway.register_adapter(
            BackgroundTasksAdapter(max_subagent_depth=config.max_subagent_depth)
        )
    # Opt-in agent scheduling (spec 049): register the four scheduling tools only when a
    # non-zero count cap is set (0 → no tools, byte-identical). The supervisor is built
    # per-run by the scope owner; the tools read it via RunContext.schedules.
    if config.max_schedules >= 1:
        from loopplane.tools.scheduling import SchedulingToolsAdapter

        gateway.register_adapter(
            SchedulingToolsAdapter(max_subagent_depth=config.max_subagent_depth)
        )

    sink = RunSink()
    if config.observability:
        # The overlay observes events as an isolated side-branch inside RunSink's
        # guard, so a telemetry fault can never crash a run.
        sink.set_observability(maybe_attach(_noop_sink))

    controller_kwargs: dict[str, Any] = {}
    if checkpoint_store is not None:
        controller_kwargs["checkpoint_store"] = checkpoint_store
    if artifact_store is not None:
        controller_kwargs["artifact_store"] = artifact_store
    if replacement_budget_bytes is not None:
        controller_kwargs["replacement_budget_bytes"] = replacement_budget_bytes
    if memory_store is not None:
        controller_kwargs["memory_store"] = memory_store
    if skills_map:
        controller_kwargs["skills"] = skills_map
    if config.auto_compact_threshold is not None:
        controller_kwargs["auto_compact_threshold"] = config.auto_compact_threshold
    if config.compaction_summarizer is not None:
        controller_kwargs["compaction_summarizer"] = config.compaction_summarizer
    if config.max_background_tasks >= 1:
        from loopplane.tools.background import make_supervisor_factory

        controller_kwargs["background_supervisor_factory"] = make_supervisor_factory(
            _make_child_host_builder(config), config.max_background_tasks
        )
        controller_kwargs["max_background_tasks"] = config.max_background_tasks
    if config.max_schedules >= 1:
        from loopplane.tools.scheduling import make_schedule_supervisor_factory

        controller_kwargs["schedule_supervisor_factory"] = (
            make_schedule_supervisor_factory(
                _make_child_host_builder(config), config.max_schedules
            )
        )
        controller_kwargs["max_schedules"] = config.max_schedules

    controller = RuntimeController(
        model=config.model,
        gateway=gateway,
        event_sink=sink,
        plan_mode=config.plan_mode,
        subagent_depth=subagent_depth,
        **controller_kwargs,
    )
    return AssembledRuntime(
        controller=controller,
        sink=sink,
        artifact_store=artifact_store,
        checkpoint_store=checkpoint_store,
        skill_problems=skill_problems,
        gateway=gateway,
        skills=skills_map or {},
        memory_store=memory_store,
    )


def _build_decider(
    config: RuntimeConfig,
    tool_names: list[str],
    skills_map: Mapping[str, LoadedSkill] | None,
) -> PolicyDecider | None:
    """Translate the approval policy, the skill profiles, and the network-egress
    setting into a Phase-1 decider; ``None`` leaves the gateway's allow-all default
    (test posture).

    The network gate reuses the existing decide-stage combinators (spec 034): when
    egress is disabled it must be present to deny a network-flagged tool by default,
    so the composed decider is ``safe_failure(all_of(<approval?>, network_policy))``
    — deny-wins + fail-closed. The plan-mode gate (spec 038) adds one more decider
    when ``config.plan_mode`` is on; it reads the per-run ``RunContext.plan_mode``
    holder at decide time, so it is a no-op for any run whose holder is absent/inactive
    (installing it never changes a non-plan-mode run's verdicts). The permission-rule
    DSL (spec 039) adds one more decider when ``config.permission_rules`` carries any
    rule; it allows/denies/asks each call by the host's declarative rules (deny-wins,
    and ``ask`` reuses the existing approval round-trip). The ``None`` fast-path is
    preserved only when there is no approval/skills *and* egress is enabled *and* plan
    mode is off *and* no permission rules, so an existing non-network run's allow-all
    posture is unchanged.
    """

    approval_needed = config.approval is not None or bool(skills_map)
    # When egress is off the gate must be installed so network tools deny by default;
    # when on, the policy is a no-op allow and only matters if approval is also wired.
    network_gate_needed = not config.allow_network
    plan_mode_needed = config.plan_mode
    rules_needed = config.permission_rules is not None and bool(
        config.permission_rules.rules
    )
    if (
        not approval_needed
        and not network_gate_needed
        and not plan_mode_needed
        and not rules_needed
    ):
        return None

    deciders: list[PolicyDecider] = []
    if approval_needed:
        rules = [
            PermissionRule(matcher=name, effect=effect, scope="session-local")
            for name, effect in approval_effects(config, tool_names)
            if effect is not None
        ]
        profiles = skill_profiles(skills_map) if skills_map else None
        deciders.append(HumanApproval(rules=rules, skill_profiles=profiles))
    deciders.append(network_policy(allow_network=config.allow_network))
    if plan_mode_needed:
        # The context-reading form: it denies non-read-only (non-allowlisted) tools
        # only while the per-run holder is active (set by the controller when the run
        # starts in plan mode and cleared by exit_plan_mode on approval).
        deciders.append(plan_mode_policy())
    if rules_needed:
        # The declarative permission rules (spec 039): allow/deny/ask each call by the
        # host's rules; an `ask` reuses the per-run RunContext's approval round-trip.
        # Regexes are compiled here, so a malformed rule fails the build (fail-closed).
        assert config.permission_rules is not None
        deciders.append(rule_dsl_policy(config.permission_rules))

    # Deny-wins composition (all_of) wrapped fail-closed (safe_failure); a single
    # decider composes the same way, so this is uniform whether or not approval is
    # wired.
    return safe_failure(all_of(*deciders))


def _make_child_host_builder(parent_config: RuntimeConfig) -> ChildHostFactory:
    """Build the closure the spawn tool uses to create a fresh child host (spec 043).

    The child host is a full ``LoopPlaneHost`` assembled from the parent configuration
    (same model + tools + storage), at ``subagent_depth = depth`` (parent + 1), with an
    optional ``allowed_tools`` restriction. Returning a fresh host per spawn means each
    child run is isolated and starts its own session — no cross-run state leakage.
    """

    def build_child_host(
        depth: int, allowed_tools: tuple[str, ...] | None, working_scope: Path
    ) -> LoopPlaneHost:
        # Imported here (not at module scope) to break the
        # engineering → host → assembly import cycle.
        from loopplane.host.host import LoopPlaneHost

        child_config = _restrict_config(parent_config, allowed_tools)
        return LoopPlaneHost(
            child_config, working_scope=working_scope, subagent_depth=depth
        )

    return build_child_host


def _restrict_config(
    config: RuntimeConfig, allowed_tools: tuple[str, ...] | None
) -> RuntimeConfig:
    """A child ``RuntimeConfig`` restricted to ``allowed_tools`` (FR-040).

    When ``allowed_tools`` is ``None`` the child inherits the parent's tools unchanged
    (still subject to the depth cap on its own ``spawn_subagent``). Otherwise the
    child's tool set is the intersection of the parent's tools and the allowlist:
    host-declared ``ToolSpec`` tools are filtered by name, and a multi-tool
    ``ToolAdapter`` is kept only when **every** tool it advertises is allowlisted (else
    dropped whole — least privilege errs safe; the child never sees a tool outside its
    allowlist). The Tool Gateway stays the single owner of tool dispatch (Constitution
    V) — no out-of-gateway adapter wrapping. ``spawn_subagent`` is granted to the child
    only when the allowlist names it (and then the depth cap still applies).
    """

    if allowed_tools is None:
        return config
    allowed = set(allowed_tools)
    tools = tuple(spec for spec in config.tools if spec.descriptor.name in allowed)
    adapters = tuple(
        adapter
        for adapter in config.tool_adapters
        if adapter.describe()
        and all(descriptor.name in allowed for descriptor in adapter.describe())
    )
    # The spawn tool is auto-registered by ``assemble`` from ``max_subagent_depth``;
    # drop it for the child unless explicitly allowlisted.
    max_depth = config.max_subagent_depth if "spawn_subagent" in allowed else 0
    return dataclasses.replace(
        config, tools=tools, tool_adapters=adapters, max_subagent_depth=max_depth
    )
