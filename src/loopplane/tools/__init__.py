"""The Internal Tool Adapter and the baseline tool set (FR-030–FR-034), the Web Tool
Adapter and its host-injected search seam (spec 034), and the Subagent Spawn Tool
Adapter (spec 043)."""

from loopplane.tools.background import BackgroundTasksAdapter, BackgroundTaskSupervisor
from loopplane.tools.container import DockerCommandExecutor
from loopplane.tools.execution import (
    CommandExecutor,
    CommandResult,
    HostCommandExecutor,
    LocalJailCommandExecutor,
    ResourceLimits,
)
from loopplane.tools.internal import InternalToolAdapter
from loopplane.tools.messaging import SwarmSupervisor, SwarmToolsAdapter
from loopplane.tools.scheduling import ScheduleSupervisor, SchedulingToolsAdapter
from loopplane.tools.search import ReferenceSearchProvider
from loopplane.tools.subagent import SpawnSubagentAdapter
from loopplane.tools.web import SearchProvider, SearchResult, WebToolAdapter
from loopplane.tools.worktree import WorktreeManager, WorktreeToolsAdapter

__all__ = [
    "BackgroundTaskSupervisor",
    "BackgroundTasksAdapter",
    "CommandExecutor",
    "CommandResult",
    "DockerCommandExecutor",
    "HostCommandExecutor",
    "InternalToolAdapter",
    "LocalJailCommandExecutor",
    "ReferenceSearchProvider",
    "ResourceLimits",
    "ScheduleSupervisor",
    "SchedulingToolsAdapter",
    "SearchProvider",
    "SearchResult",
    "SpawnSubagentAdapter",
    "SwarmSupervisor",
    "SwarmToolsAdapter",
    "WebToolAdapter",
    "WorktreeManager",
    "WorktreeToolsAdapter",
]
