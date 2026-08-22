"""Runtime Configuration: the declarative, public-safe composition contract a
host hands to ``LoopPlaneHost`` (spec FR-010–FR-015).

The configuration is a programmatic object, also constructible from a plain
mapping via :meth:`RuntimeConfig.from_mapping`; no configuration-file format is
in scope this phase. It carries **no secrets** — credentials live in the
host-supplied model object or the host environment, never here (FR-013).
"""

from __future__ import annotations

import importlib.util
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from loopplane.approval import RuleEffect
from loopplane.fairness import PlatformFairnessGate
from loopplane.gateway import ToolAdapter, ToolHandler
from loopplane.governance import (
    PERMISSION_MODES,
    PermissionRuleSet,
    PermissionRuleSpec,
)
from loopplane.host.capabilities import (
    AllowedWorkspaceContextProvider,
    ManagedMcpAuthorizationHandler,
    ManagedMcpEndpointPolicy,
    ManagedMcpTokenStore,
    ManagedScheduleRunner,
)
from loopplane.host.storage_authority import StorageAuthorityFactory
from loopplane.ledger import UsdLedger
from loopplane.model import ModelBoundary, ToolDescriptor
from loopplane.pricing import PricingTable

ApprovalDefault = Literal["allow", "ask", "deny"]
CheckpointBackend = Literal["file", "sqlite"]


class ConfigError(ValueError):
    """Raised at assembly when a :class:`RuntimeConfig` is invalid, incomplete,
    or internally inconsistent (FR-005).

    The message is field-level and public-safe; it never carries a secret or a
    private path (FR-013).
    """


@dataclass(frozen=True)
class ToolSpec:
    """A single internal tool: its descriptor plus the handler the Tool Gateway
    invokes (FR-022)."""

    descriptor: ToolDescriptor
    handler: ToolHandler


@dataclass(frozen=True)
class ApprovalPolicy:
    """Allow / deny / ask selection per tool, delegated to the Phase-1 Human
    Approval boundary (FR-014). ``default`` decides tools named in none of the
    sets; an ``ask`` tool escalates to the host approval handler (or denies when
    no handler is supplied)."""

    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    ask: frozenset[str] = frozenset()
    default: ApprovalDefault = "allow"


@dataclass(frozen=True)
class StorageConfig:
    """Durable checkpoint + artifact backends under one host-chosen base
    directory (host-overridable; FR-002). Both are wired together — the host
    never connects the artifact handoff by hand."""

    root: Path
    artifact_threshold_bytes: int | None = None
    replacement_budget_bytes: int | None = None
    checkpoint_backend: CheckpointBackend = "file"
    authority: StorageAuthorityFactory | None = None


@dataclass(frozen=True)
class MemoryConfig:
    """A directory of durable memory entries (optional; off by default)."""

    source: Path


@dataclass(frozen=True)
class SkillsConfig:
    """Directories of declarative skill packages (optional; off by default)."""

    sources: tuple[Path, ...]


@dataclass(frozen=True)
class CapabilityManagementConfig:
    """Host-owned gates and collaborators for durable capability settings."""

    mutations_enabled: bool = False
    runtime_activation_enabled: bool = False
    mcp_endpoint_policy: ManagedMcpEndpointPolicy | None = None
    schedule_runner: ManagedScheduleRunner | None = None
    allowed_context_provider: AllowedWorkspaceContextProvider | None = None
    # 084 — the host's half of an interactive MCP authorization (ADR 0019 D1/D2).
    # Collaborators, like the policy and runner above; not RuntimeConfig knobs, so
    # the credential path never passes through the run configuration. Both absent
    # means this deployment cannot authorize interactively — the fail-closed
    # default, which is what a headless or CI process should be.
    mcp_authorization_handler: ManagedMcpAuthorizationHandler | None = None
    mcp_token_store: ManagedMcpTokenStore | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    """The minimal declarative composition of a run (FR-010).

    Only ``model`` is required. Every optional subsystem defaults to off, so an
    otherwise-empty config behaves exactly like the bare Phase-1 loop (FR-012).
    """

    model: ModelBoundary
    tools: tuple[ToolSpec, ...] = ()
    tool_adapters: tuple[ToolAdapter, ...] = ()
    approval: ApprovalPolicy | None = None
    storage: StorageConfig | None = None
    memory: MemoryConfig | None = None
    skills: SkillsConfig | None = None
    capability_management: CapabilityManagementConfig | None = None
    observability: bool = False
    # Opt-in network egress (spec 034): off by default, so a network-flagged tool
    # is denied at the Gateway's decide stage unless the host turns this on. Carries
    # no secret — a search provider's credential lives in the host-supplied provider.
    allow_network: bool = False
    # Opt-in plan mode (spec 038): off by default. When on, a run starts in plan mode
    # — the agent may only use read-only tools (plus ask_user / exit_plan_mode) until a
    # human approves a submitted plan, enforced at the Gateway's decide stage. Carries
    # no secret. Default off → existing runs are unchanged.
    plan_mode: bool = False
    # Opt-in declarative permission rules (spec 039): None by default. When supplied, a
    # rule_dsl_policy is composed into the Gateway's decide stage to allow/deny/ask each
    # call by the host's declarative rules (deny-wins, fail-closed). Carries no secret —
    # a rule is only a tool name + patterns + a decision. Default None → existing runs
    # are unchanged (no DSL policy installed).
    permission_rules: PermissionRuleSet | None = None
    # Opt-in named permission mode (spec 066; gap G10): None by default. When set to a
    # known mode (acceptEdits / bypassPermissions / dontAsk / plan) the assembler
    # derives a preset PermissionRuleSet from the EXISTING 039 DSL (or sets plan mode)
    # and feeds it through the SAME rule_dsl_policy decider — a convenience over
    # hand-authored rules; no new decider/stage. None → no preset, byte-identical. A
    # bare string; carries no secret. acceptEdits/bypassPermissions are mutually
    # exclusive with permission_rules (validated); dontAsk/plan may combine with them.
    permission_mode: str | None = None
    # Browser-selectable per-run permission modes (spec 077). This is a distinct
    # host-owned allow-list: it is empty by default, so browser callers retain the
    # existing behavior unless an embedding host explicitly exposes a mode.
    browser_permission_modes: tuple[str, ...] = ()
    # Opt-in proactive auto-compaction threshold (spec 041): None by default. When a
    # fraction f in (0, 1] is supplied, the prompt assembler compacts history (the
    # existing mechanical digest) before a turn once the estimated assembled-context
    # size reaches f * model.context_capacity() — a safety margin before the model's
    # limit. None reuses the existing full-capacity proactive check, so the default-off
    # path is byte-identical to today. Carries no secret (a plain fraction). The
    # reactive ContextOverflowError compact-and-retry-once backstop is unchanged.
    auto_compact_threshold: float | None = None
    # Opt-in cheap-model compaction summarizer (spec 042): None by default. When a
    # host supplies a (typically cheap) summarizer ModelBoundary, compaction asks it
    # to summarize the dropped conversation span and stores the model summary in the
    # existing SummaryMarkerBlock (replacing the mechanical excerpts; keeping
    # turn_count / tool_names). It is a FAIL-SAFE overlay: any summarizer failure
    # (exception, timeout, empty output) falls back to the mechanical digest and
    # never breaks a run. None → the mechanical digest, byte-identical to today.
    # An object collaborator like `model`; carries no secret (a summarizer's
    # credential lives in the host-supplied model object, never here).
    compaction_summarizer: ModelBoundary | None = None
    # Opt-in model-driven subagent spawning (spec 043): the hard recursion-depth cap.
    # Off by default (`0` → NO `spawn_subagent` tool is registered, so a run is
    # byte-identical to today). When a host sets it >= 1, a `spawn_subagent` gateway
    # tool is registered that runs ONE bounded child agent through the existing Phase-3
    # run_loop and returns its final text; the tool DENIES a spawn (a normalized error,
    # no child run) once a run's `RunContext.subagent_depth` reaches this cap, so
    # subagents cannot nest without bound (a child runs at parent depth + 1). A value of
    # `1` enables exactly one level. Carries no secret (a bare integer).
    max_subagent_depth: int = 0
    # Opt-in background tasks (spec 048; ADR 0002): the per-run count cap. Off by
    # default (`0` → NO background-task tools registered, byte-identical). When a host
    # sets it >= 1 (with `max_subagent_depth` >= 1 — the 043 depth cap a background
    # child run is subject to), the five background-task tools are registered and a run
    # may have up to this many concurrent tasks. A bare integer; carries no secret.
    max_background_tasks: int = 0
    # Opt-in agent scheduling (spec 049): the per-run schedule count cap. Off by default
    # (`0` → NO scheduling tools registered, byte-identical). When a host sets it >= 1
    # (with `max_subagent_depth` >= 1, the depth cap a scheduled child obeys), the four
    # scheduling tools are registered and a run may have up to this many active
    # schedules. A bare integer; carries no secret.
    max_schedules: int = 0
    # Opt-in agent-to-agent messaging & swarm (spec 050; ADR 0003): the per-run team
    # cap. Off by default (`0` → NO swarm tools registered, byte-identical). When a
    # host sets it >= 1 (with `max_subagent_depth` >= 1), the five swarm tools are
    # registered and a run may dispatch up to this many members. A bare integer.
    max_swarm_members: int = 0
    # The per-run message cap for spec 050 (the total in-run agent-to-agent messages). A
    # bare integer; carries no secret.
    max_swarm_messages: int = 0
    # Opt-in worktree isolation (spec 051): the per-run managed-worktree cap. Off by
    # default (`0` → NO worktree tools registered, byte-identical). When a host sets it
    # >= 1, the three worktree tools are registered and a run may create up to this many
    # isolated git worktrees under a managed area of the working scope. A bare integer;
    # carries no secret.
    max_worktrees: int = 0
    # Opt-in USD budget caps (spec 055; G22 Phase B; ADR 0005): per-message +
    # per-session USD caps enforced INSIDE the Agent Loop turn cycle (TokenUsage). All
    # None (default) → no cost accounting, no enforcement, byte-identical. Enforcement
    # also requires `pricing_table` + `model_id` (the host supplies both; the model
    # boundary exposes no model id). When a cap is crossed the run terminates with a new
    # `budget-exceeded` TerminationReason (additive, no SCHEMA_VERSION bump). Decimal
    # money; carries no secret.
    per_message_usd: Decimal | None = None
    per_session_usd: Decimal | None = None
    # The host-supplied 053 pricing table + model-id used to price token usage for the
    # caps above. Both None by default → the caps are inert (no enforcement).
    pricing_table: PricingTable | None = None
    model_id: str | None = None
    # Opt-in per-user-monthly USD cap (spec 063; G22 Phase C; ADR 0010): a host-supplied
    # durable `usd_ledger` + the monthly cap. Both None (default) → no monthly
    # enforcement, byte-identical. Also requires `pricing_table` + `model_id` (the cost
    # source). Reuses the `budget-exceeded` reason (no SCHEMA_VERSION bump). Decimal
    # money; the ledger/DSN carries no secret in this config object.
    per_user_monthly_usd: Decimal | None = None
    usd_ledger: UsdLedger | None = None
    # Opt-in pre-turn predictive cost guard (spec 068; ADR 0014): None by
    # default. When set, this host-owned max-output token estimate is combined
    # with assembled request-token estimation before the model call. It does not
    # alter provider generation limits. A bare non-negative integer; carries no
    # secret.
    pre_turn_max_output_tokens: int | None = None
    # Opt-in in-process platform fairness (spec 072; ADR 0013): None by default.
    # The host-supplied collaborator gates tenant admission and model-turn starts.
    # It carries no secret; tenant ids are existing opaque principal ids.
    platform_fairness: PlatformFairnessGate | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> RuntimeConfig:
        """Build a config from a plain mapping (FR-011).

        Object-typed collaborators (``model``, tool handlers, adapters) pass
        through as objects; scalar/structured selections (storage root,
        approval sets, flags) are coerced. No file is read — the mapping is
        already in memory.
        """

        if "model" not in data or data["model"] is None:
            raise ConfigError("configuration mapping must provide a 'model'")
        return cls(
            model=data["model"],
            tools=tuple(_coerce_tool(item) for item in data.get("tools", ())),
            tool_adapters=tuple(data.get("tool_adapters", ())),
            approval=_coerce_approval(data.get("approval")),
            storage=_coerce_storage(data.get("storage")),
            memory=_coerce_memory(data.get("memory")),
            skills=_coerce_skills(data.get("skills")),
            capability_management=_coerce_capability_management(
                data.get("capability_management")
            ),
            observability=bool(data.get("observability", False)),
            allow_network=bool(data.get("allow_network", False)),
            plan_mode=bool(data.get("plan_mode", False)),
            permission_rules=_coerce_permission_rules(data.get("permission_rules")),
            permission_mode=data.get("permission_mode"),
            browser_permission_modes=tuple(data.get("browser_permission_modes", ())),
            auto_compact_threshold=_coerce_threshold(
                data.get("auto_compact_threshold")
            ),
            compaction_summarizer=data.get("compaction_summarizer"),
            max_subagent_depth=int(data.get("max_subagent_depth", 0)),
            max_background_tasks=int(data.get("max_background_tasks", 0)),
            max_schedules=int(data.get("max_schedules", 0)),
            max_swarm_members=int(data.get("max_swarm_members", 0)),
            max_swarm_messages=int(data.get("max_swarm_messages", 0)),
            max_worktrees=int(data.get("max_worktrees", 0)),
            per_message_usd=_coerce_usd(data.get("per_message_usd")),
            per_session_usd=_coerce_usd(data.get("per_session_usd")),
            pricing_table=data.get("pricing_table"),
            model_id=data.get("model_id"),
            per_user_monthly_usd=_coerce_usd(data.get("per_user_monthly_usd")),
            usd_ledger=data.get("usd_ledger"),
            pre_turn_max_output_tokens=_coerce_optional_non_negative_int(
                data.get("pre_turn_max_output_tokens"),
                field="pre_turn_max_output_tokens",
            ),
            platform_fairness=data.get("platform_fairness"),
        )


def _coerce_usd(value: Any) -> Decimal | None:
    if value is None or isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_optional_non_negative_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(f"{field} must be a non-negative integer")
    return value


def _coerce_tool(item: Any) -> ToolSpec:
    if isinstance(item, ToolSpec):
        return item
    descriptor, handler = item
    return ToolSpec(descriptor=descriptor, handler=handler)


def _coerce_approval(value: Any) -> ApprovalPolicy | None:
    if value is None or isinstance(value, ApprovalPolicy):
        return value
    return ApprovalPolicy(
        allow=frozenset(value.get("allow", ())),
        deny=frozenset(value.get("deny", ())),
        ask=frozenset(value.get("ask", ())),
        default=value.get("default", "allow"),
    )


def _coerce_storage(value: Any) -> StorageConfig | None:
    if value is None or isinstance(value, StorageConfig):
        return value
    if isinstance(value, str | Path):
        return StorageConfig(root=Path(value))
    return StorageConfig(
        root=Path(value["root"]),
        artifact_threshold_bytes=value.get("artifact_threshold_bytes"),
        replacement_budget_bytes=value.get("replacement_budget_bytes"),
        checkpoint_backend=value.get("checkpoint_backend", "file"),
        authority=value.get("authority"),
    )


def _coerce_memory(value: Any) -> MemoryConfig | None:
    if value is None or isinstance(value, MemoryConfig):
        return value
    if isinstance(value, str | Path):
        return MemoryConfig(source=Path(value))
    return MemoryConfig(source=Path(value["source"]))


def _coerce_skills(value: Any) -> SkillsConfig | None:
    if value is None or isinstance(value, SkillsConfig):
        return value
    sources = value["sources"] if isinstance(value, Mapping) else value
    return SkillsConfig(sources=tuple(Path(p) for p in sources))


def _coerce_capability_management(
    value: Any,
) -> CapabilityManagementConfig | None:
    if value is None or isinstance(value, CapabilityManagementConfig):
        return value
    if not isinstance(value, Mapping):
        raise ConfigError("capability_management must be a mapping")
    return CapabilityManagementConfig(
        mutations_enabled=bool(value.get("mutations_enabled", False)),
        runtime_activation_enabled=bool(value.get("runtime_activation_enabled", False)),
        mcp_endpoint_policy=value.get("mcp_endpoint_policy"),
        schedule_runner=value.get("schedule_runner"),
        allowed_context_provider=value.get("allowed_context_provider"),
    )


def _coerce_permission_rules(value: Any) -> PermissionRuleSet | None:
    """Coerce the declarative permission rules (spec 039): a ``PermissionRuleSet``
    passes through; a mapping ``{"rules": [{tool, match?, decision}, ...], "default":
    ...}`` is built into one; ``None`` stays ``None`` (no DSL policy)."""

    if value is None or isinstance(value, PermissionRuleSet):
        return value
    rules = tuple(
        rule if isinstance(rule, PermissionRuleSpec) else PermissionRuleSpec(**rule)
        for rule in value.get("rules", ())
    )
    return PermissionRuleSet(rules=rules, default=value.get("default", "allow"))


def _coerce_threshold(value: Any) -> float | None:
    """Coerce the auto-compaction threshold (spec 041): ``None`` stays ``None``;
    anything else becomes a ``float`` (range-checked later by ``validate_config``)."""

    if value is None:
        return None
    return float(value)


def _otel_available() -> bool:
    return importlib.util.find_spec("opentelemetry") is not None


def _observability_active() -> bool:
    """Whether the metadata-only overlay would actually attach — the same gate
    ``loopplane.observability.maybe_attach`` uses (the exporter endpoint env var
    plus the ``otel`` extra). Validating against this avoids accepting an
    ``observability=True`` that would silently produce no telemetry."""

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    return _otel_available()


def collect_tool_names(config: RuntimeConfig) -> list[str]:
    """Every tool name a config will register, before the gateway is built."""

    names: list[str] = [spec.descriptor.name for spec in config.tools]
    for adapter in config.tool_adapters:
        names.extend(descriptor.name for descriptor in adapter.describe())
    return names


def validate_config(config: RuntimeConfig) -> None:
    """Fail fast on an invalid, incomplete, or inconsistent config (FR-005).

    Raises :class:`ConfigError` before any runtime component is built. The
    skill-adapter tool names are not known here; duplicate detection covers the
    host-declared tools and adapters (skill names are validated by the loader).
    """

    if config.model is None:
        raise ConfigError("a model provider is required")
    if config.storage is not None and config.storage.authority is not None:
        if config.storage.checkpoint_backend != "sqlite":
            raise ConfigError(
                "storage authority requires the sqlite checkpoint backend"
            )
        if not callable(getattr(config.storage.authority, "acquire", None)):
            raise ConfigError("storage authority must provide acquire()")
    if config.platform_fairness is not None:
        for name in ("admit", "model_turn"):
            if not callable(getattr(config.platform_fairness, name, None)):
                raise ConfigError(
                    "platform_fairness must provide admit() and model_turn()"
                )

    capability_management = config.capability_management
    if capability_management is not None:
        endpoint_policy = capability_management.mcp_endpoint_policy
        if endpoint_policy is not None and not callable(endpoint_policy):
            raise ConfigError(
                "capability_management.mcp_endpoint_policy must be callable"
            )
        schedule_runner = capability_management.schedule_runner
        if schedule_runner is not None and not callable(
            getattr(schedule_runner, "run_now", None)
        ):
            raise ConfigError(
                "capability_management.schedule_runner must provide run_now()"
            )
        allowed_context_provider = capability_management.allowed_context_provider
        if allowed_context_provider is not None and not callable(
            allowed_context_provider
        ):
            raise ConfigError(
                "capability_management.allowed_context_provider must be callable"
            )

    names = collect_tool_names(config)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        raise ConfigError(f"duplicate tool names: {sorted(duplicates)}")

    if config.approval is not None:
        referenced = config.approval.allow | config.approval.deny | config.approval.ask
        unknown = referenced - set(names)
        if unknown:
            raise ConfigError(
                f"approval policy references unregistered tools: {sorted(unknown)}"
            )

    if config.observability and not _observability_active():
        raise ConfigError(
            "observability is enabled but the telemetry overlay would not "
            "activate: install the 'otel' extra and set "
            "OTEL_EXPORTER_OTLP_ENDPOINT"
        )

    threshold = config.auto_compact_threshold
    if threshold is not None and not (math.isfinite(threshold) and 0 < threshold <= 1):
        raise ConfigError("auto_compact_threshold must be a number in (0, 1]")

    if config.max_subagent_depth < 0:
        raise ConfigError("max_subagent_depth must be a non-negative integer")

    if config.max_background_tasks < 0:
        raise ConfigError("max_background_tasks must be a non-negative integer")

    if config.max_schedules < 0:
        raise ConfigError("max_schedules must be a non-negative integer")

    if config.max_swarm_members < 0:
        raise ConfigError("max_swarm_members must be a non-negative integer")

    if config.max_swarm_messages < 0:
        raise ConfigError("max_swarm_messages must be a non-negative integer")

    if config.max_worktrees < 0:
        raise ConfigError("max_worktrees must be a non-negative integer")

    if config.permission_mode is not None:
        if config.permission_mode not in PERMISSION_MODES:
            raise ConfigError(
                f"unknown permission_mode {config.permission_mode!r}; "
                f"expected one of {list(PERMISSION_MODES)}"
            )
        # acceptEdits / bypassPermissions are standalone presets — combining them with
        # hand-authored permission_rules is ambiguous; dontAsk/plan may combine.
        if (
            config.permission_mode in ("acceptEdits", "bypassPermissions")
            and config.permission_rules is not None
        ):
            raise ConfigError(
                f"permission_mode {config.permission_mode!r} cannot be combined with "
                "permission_rules; set one or the other"
            )

    for _label, _cap in (
        ("per_message_usd", config.per_message_usd),
        ("per_session_usd", config.per_session_usd),
        ("per_user_monthly_usd", config.per_user_monthly_usd),
    ):
        if _cap is not None and _cap < 0:
            raise ConfigError(f"{_label} must be a non-negative USD amount")

    _coerce_optional_non_negative_int(
        config.pre_turn_max_output_tokens,
        field="pre_turn_max_output_tokens",
    )


def approval_effects(
    config: RuntimeConfig, tool_names: Sequence[str]
) -> list[tuple[str, RuleEffect | None]]:
    """Resolve each registered tool to allow / deny / ask (``None`` = ask).

    Used by the Reference Runner to translate an :class:`ApprovalPolicy` into
    Phase-1 permission rules; ``None`` means "no rule" so the Human Approval
    boundary escalates that tool to the reviewer.
    """

    policy = config.approval or ApprovalPolicy()
    effects: list[tuple[str, RuleEffect | None]] = []
    for name in tool_names:
        effect: RuleEffect | None
        if name in policy.deny:
            effect = "deny"
        elif name in policy.ask:
            effect = None
        elif name in policy.allow:
            effect = "allow"
        elif policy.default == "deny":
            effect = "deny"
        elif policy.default == "ask":
            effect = None
        else:
            effect = "allow"
        effects.append((name, effect))
    return effects
