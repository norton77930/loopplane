"""Public-safe capability management projections for the web host (075)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

CapabilityStatus = Literal[
    "available",
    "connected",
    "disconnected",
    "deleted",
    "disabled",
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
    tools: tuple[str, ...] = ()
    problem: str | None = None
    updated_at: datetime | None = None
    owner_id: str | None = None


@dataclass(frozen=True)
class WorkspaceContext:
    id: str
    name: str
    description: str
    workspace_label: str
    status: CapabilityStatus = "available"
    updated_at: datetime | None = None
    owner_id: str | None = None


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
    status: CapabilityStatus = "disabled"
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    problem: str | None = None


@dataclass(frozen=True)
class ModelDefault:
    model_id: str | None
    label: str | None
    status: CapabilityStatus
    updated_at: datetime | None = None
