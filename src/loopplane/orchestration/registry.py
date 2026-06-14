"""The agent registry for multi-agent orchestration (013).

A registry of named subagents — each a Phase-3 ``LoopDefinition``. Names are kept
in registration order (the deterministic order the coordinator runs and aggregates
by). Composes only the public Phase-3 loop surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopplane.engineering import LoopDefinition


class DuplicateSubagentError(ValueError):
    """Raised when registering a subagent name that is already registered
    (FR-001). The message is public-safe."""


@dataclass(frozen=True)
class Subagent:
    """A named subagent: the public name and the loop definition it runs."""

    name: str
    definition: LoopDefinition


class AgentRegistry:
    """A registry of named subagents, addressable by name in registration
    order."""

    def __init__(self) -> None:
        self._subagents: dict[str, Subagent] = {}

    def register(self, name: str, definition: LoopDefinition) -> Subagent:
        """Register a named subagent; a duplicate name raises (FR-001)."""

        if name in self._subagents:
            raise DuplicateSubagentError(f"subagent already registered: {name}")
        subagent = Subagent(name=name, definition=definition)
        self._subagents[name] = subagent
        return subagent

    def get(self, name: str) -> Subagent | None:
        """The registered subagent, or ``None`` when unknown (FR-003)."""

        return self._subagents.get(name)

    def names(self) -> tuple[str, ...]:
        """Registered names in registration order (the deterministic order)."""

        return tuple(self._subagents)

    def __contains__(self, name: object) -> bool:
        return name in self._subagents
