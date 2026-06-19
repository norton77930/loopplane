"""The Reference Runner: maps a :class:`RuntimeConfig` onto wired Phase-1
components (spec FR-020–FR-024).

This is the single assembly path. ``LoopPlaneHost`` and the example runner both
go through :func:`assemble`, so smoke tests exercise the real embedding path and
there is never a second, divergent wiring (FR-024). It composes Phase-1
components only through their declared interfaces and re-implements none of them
(FR-060).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
from loopplane.governance import all_of, network_policy, safe_failure
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


def assemble(config: RuntimeConfig) -> AssembledRuntime:
    """Validate and wire a runtime from a configuration (FR-020, FR-005)."""

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

    controller = RuntimeController(
        model=config.model,
        gateway=gateway,
        event_sink=sink,
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
    — deny-wins + fail-closed. The ``None`` fast-path is preserved only when there is
    no approval/skills *and* egress is enabled (the network policy would be a harmless
    allow), so an existing non-network run's allow-all posture is unchanged.
    """

    approval_needed = config.approval is not None or bool(skills_map)
    # When egress is off the gate must be installed so network tools deny by default;
    # when on, the policy is a no-op allow and only matters if approval is also wired.
    network_gate_needed = not config.allow_network
    if not approval_needed and not network_gate_needed:
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

    # Deny-wins composition (all_of) wrapped fail-closed (safe_failure); a single
    # decider composes the same way, so this is uniform whether or not approval is
    # wired.
    return safe_failure(all_of(*deciders))
