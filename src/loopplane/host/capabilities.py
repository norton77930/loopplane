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
    "needs_authorization",
    "read_only",
    "running",
    "unavailable",
]

# 084 — the authorization *mode* of a managed MCP server. A mode, never a
# credential: this record is persisted inside the LoopPlane profile root, which is
# inside the backup whitelist, so material must never reach it (ADR 0019 D8).
ManagedMcpAuthorization = Literal["interactive"]


class ManagedMcpAuthorizationHandler(Protocol):
    """The host's half of an interactive MCP authorization (084; ADR 0019 D1).

    Declared here rather than imported from ``loopplane.adapters.mcp.oauth`` so the
    host→adapters edge stays confined to the one file that already declares it
    (``host/_capability_mcp.py``). Protocols are structural, so an object written
    against the adapter's protocol satisfies this one automatically;
    ``tests/contract/test_mcp_oauth_boundary.py`` pins the two shapes together so
    the duplication cannot drift.
    """

    def redirect_uri(self, *, server: str) -> str: ...

    async def present(
        self, url: str, *, server: str, principal: str | None
    ) -> None: ...

    async def await_result(self, *, server: str, principal: str | None) -> object: ...


class ManagedMcpTokenStore(Protocol):
    """Where authorization material lives — the host's decision (ADR 0019 D3).

    ``material`` is deliberately opaque at this boundary: the host layer stores and
    returns it and has no business inspecting it, and a type it cannot read is a
    type it cannot accidentally log.
    """

    async def load(self, *, principal: str | None, server: str) -> object | None: ...

    async def save(
        self, *, principal: str | None, server: str, material: object
    ) -> None: ...

    async def discard(self, *, principal: str | None, server: str) -> None: ...


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
    # 084 — which authorization mode this server uses, never any material (D8).
    authorization: ManagedMcpAuthorization | None = None


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
