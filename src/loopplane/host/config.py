"""Runtime Configuration: the declarative, public-safe composition contract a
host hands to ``LoopPlaneHost`` (spec FR-010–FR-015).

The configuration is a programmatic object, also constructible from a plain
mapping via :meth:`RuntimeConfig.from_mapping`; no configuration-file format is
in scope this phase. It carries **no secrets** — credentials live in the
host-supplied model object or the host environment, never here (FR-013).
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from loopplane.approval import RuleEffect
from loopplane.gateway import ToolAdapter, ToolHandler
from loopplane.model import ModelBoundary, ToolDescriptor

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


@dataclass(frozen=True)
class MemoryConfig:
    """A directory of durable memory entries (optional; off by default)."""

    source: Path


@dataclass(frozen=True)
class SkillsConfig:
    """Directories of declarative skill packages (optional; off by default)."""

    sources: tuple[Path, ...]


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
            observability=bool(data.get("observability", False)),
            allow_network=bool(data.get("allow_network", False)),
            plan_mode=bool(data.get("plan_mode", False)),
        )


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
