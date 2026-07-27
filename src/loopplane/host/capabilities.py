"""Public-safe capability management projections for the web host (075)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit

CapabilityScope = Literal["owned", "shared_read_only"]
CapabilityAction = Literal[
    "open",
    "create",
    "update",
    "delete",
    "import",
    "reconnect",
    "bind",
    "enable",
    "disable",
    "run_now",
    "set",
    "clear",
]
ManagedMcpTransport = Literal["http", "sse", "websocket"]


def is_valid_managed_mcp_endpoint(transport: str, endpoint: str, /) -> bool:
    """Return whether a browser-managed MCP endpoint is structurally safe."""

    schemes = {
        "http": {"http", "https"},
        "sse": {"http", "https"},
        "websocket": {"ws", "wss"},
    }
    allowed_schemes = schemes.get(transport)
    candidate = endpoint.strip()
    if allowed_schemes is None or not candidate:
        return False
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return False
    del port
    return bool(
        parsed.scheme.lower() in allowed_schemes
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


CapabilityStatus = Literal[
    "available",
    "connected",
    "disconnected",
    "deleted",
    "disabled",
    "disabled_by_policy",
    "enabled",
    "failed",
    "fallback",
    "invalid",
    "read_only",
    "running",
    "unavailable",
]


@dataclass(frozen=True)
class ManagedMemoryEntry:
    id: str
    name: str
    kind: str
    description: str
    snippet: str
    status: CapabilityStatus = "available"
    updated_at: datetime | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()
    problem: str | None = None


@dataclass(frozen=True)
class ManagedMemoryDetail(ManagedMemoryEntry):
    content: str = ""
    problem: str | None = None


@dataclass(frozen=True)
class ManagedSkill:
    id: str
    name: str
    description: str
    source: str
    status: CapabilityStatus = "available"
    problem: str | None = None
    updated_at: datetime | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()


@dataclass(frozen=True)
class ManagedSkillDetail(ManagedSkill):
    instructions: str = ""


@dataclass(frozen=True)
class CapabilityOperationResult:
    ok: bool
    resource_id: str | None
    status: CapabilityStatus
    message: str


@dataclass(frozen=True)
class ManagedMcpConfiguration:
    id: str
    name: str
    status: CapabilityStatus
    tool_count: int
    transport: ManagedMcpTransport | None = None
    url: str | None = None
    tools: tuple[str, ...] = ()
    problem: str | None = None
    updated_at: datetime | None = None
    owner_id: str | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()


@dataclass(frozen=True)
class WorkspaceContext:
    id: str
    name: str
    description: str
    workspace_label: str
    status: CapabilityStatus = "available"
    updated_at: datetime | None = None
    owner_id: str | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()
    problem: str | None = None


@dataclass(frozen=True)
class SessionContextBinding:
    session_id: str
    context_id: str
    name: str
    workspace_label: str
    status: CapabilityStatus = "available"


@dataclass(frozen=True)
class ManagedSchedule:
    id: str
    name: str
    description: str
    trigger: str
    enabled: bool
    instruction: str = ""
    status: CapabilityStatus = "disabled"
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    problem: str | None = None
    owner_id: str | None = None
    updated_at: datetime | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()


@dataclass(frozen=True)
class ModelDefault:
    model_id: str | None
    label: str | None
    status: CapabilityStatus
    updated_at: datetime | None = None
    scope: CapabilityScope = "owned"
    actions: tuple[CapabilityAction, ...] = ()
    problem: str | None = None


@dataclass(frozen=True)
class CapabilitySettingsStatus:
    storage_available: bool
    mutations_enabled: bool
    runtime_activation_enabled: bool
    mcp_endpoint_policy_available: bool
    schedule_runner_available: bool


class ManagedMcpEndpointPolicy(Protocol):
    """Host-owned allow/deny callback for browser-managed network MCP."""

    def __call__(
        self,
        principal_id: str,
        transport: ManagedMcpTransport,
        endpoint: str,
        /,
    ) -> bool: ...


class AllowedWorkspaceContextProvider(Protocol):
    """Host-owned source of workspace contexts allowed to one principal."""

    def __call__(self, principal_id: str, /) -> Sequence[WorkspaceContext]: ...


class ManagedScheduleRunner(Protocol):
    """Host-owned dispatcher used by the additive schedule run-now action."""

    def run_now(self, principal_id: str, schedule: ManagedSchedule, /) -> None: ...
