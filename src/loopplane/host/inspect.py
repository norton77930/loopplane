"""Read-only, metadata-only projections of the agent's capabilities/context (unit 027).

Pure functions over the existing layers (loaded skills, the gateway's tool descriptors,
MCP servers from the ``external-server:{name}`` source, and the memory store). They keep
only safe metadata (never a skill's ``instructions``, an MCP config's ``args``/``url``,
raw tool I/O, or an unbounded body) and execute nothing (FR-007).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from loopplane.memory.store import MemoryEntry
from loopplane.model.boundary import ToolDescriptor
from loopplane.skills.loader import LoadedSkill

SNIPPET_LIMIT = 200
_MCP_SOURCE_PREFIX = "external-server:"


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    autonomous: bool
    approval_required: bool
    source: str


@dataclass(frozen=True)
class ToolInfo:
    name: str
    description: str
    read_only: bool
    source: str


@dataclass(frozen=True)
class McpServerInfo:
    name: str
    tools: tuple[str, ...]


@dataclass(frozen=True)
class MemoryEntryInfo:
    type: str
    name: str
    description: str
    snippet: str


def skills_view(skills: Mapping[str, LoadedSkill]) -> tuple[SkillInfo, ...]:
    """Project loaded skills to safe metadata (drops ``instructions``)."""
    infos = [
        SkillInfo(
            name=loaded.skill.name,
            description=loaded.skill.description,
            autonomous=loaded.skill.profile.autonomous_invocation == "allowed",
            approval_required=loaded.skill.profile.approval_required,
            source=loaded.source,
        )
        for loaded in skills.values()
    ]
    return tuple(sorted(infos, key=lambda info: info.name))


def tools_view(descriptors: Sequence[ToolDescriptor]) -> tuple[ToolInfo, ...]:
    """Project registered tool descriptors to safe metadata (no execution)."""
    infos = [
        ToolInfo(
            name=descriptor.name,
            description=descriptor.description,
            read_only=descriptor.read_only,
            source=descriptor.source,
        )
        for descriptor in descriptors
    ]
    return tuple(sorted(infos, key=lambda info: info.name))


def mcp_view(descriptors: Sequence[ToolDescriptor]) -> tuple[McpServerInfo, ...]:
    """Derive connected MCP servers + their tools from the descriptors whose source is
    ``external-server:{name}`` — never the MCP config's secret-bearing args/url."""
    servers: dict[str, list[str]] = {}
    for descriptor in descriptors:
        if descriptor.source.startswith(_MCP_SOURCE_PREFIX):
            server = descriptor.source[len(_MCP_SOURCE_PREFIX) :]
            servers.setdefault(server, []).append(descriptor.name)
    return tuple(
        McpServerInfo(name=name, tools=tuple(sorted(tools)))
        for name, tools in sorted(servers.items())
    )


def _snippet(body: str) -> str:
    trimmed = body.strip()
    if len(trimmed) <= SNIPPET_LIMIT:
        return trimmed
    return trimmed[:SNIPPET_LIMIT].rstrip() + "..."


def memory_view(
    entries: Sequence[MemoryEntry], query: str | None = None
) -> tuple[MemoryEntryInfo, ...]:
    """Project memory entries to a source + bounded snippet; a non-empty ``query``
    filters by a case-insensitive match over name / description / body."""
    if query:
        needle = query.lower()
        entries = [
            entry
            for entry in entries
            if needle in entry.name.lower()
            or needle in entry.description.lower()
            or needle in entry.body.lower()
        ]
    return tuple(
        MemoryEntryInfo(
            type=entry.type,
            name=entry.name,
            description=entry.description,
            snippet=_snippet(entry.body),
        )
        for entry in entries
    )
