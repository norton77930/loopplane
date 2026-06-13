"""LoopPlane host integration layer (feature 002-loopplane-host-interface).

A thin, public-safe seam for embedding and running the Phase-1 runtime
foundation from one configured entry point. It composes Phase-1 components
through their declared interfaces and adds no runtime internals of its own.

Typical use::

    from loopplane.host import LoopPlaneHost, RuntimeConfig, ToolSpec

    host = LoopPlaneHost(RuntimeConfig(model=model, tools=(ToolSpec(desc, fn),)))
    outcome = await host.run("please echo hello", on_event=my_sink)
"""

from loopplane.host.assembly import AssembledRuntime, assemble
from loopplane.host.config import (
    ApprovalPolicy,
    ConfigError,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
    StorageConfig,
    ToolSpec,
    validate_config,
)
from loopplane.host.host import (
    ApprovalDecision,
    LoopPlaneHost,
    RunOutcome,
    Session,
    build_host,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalPolicy",
    "AssembledRuntime",
    "ConfigError",
    "LoopPlaneHost",
    "MemoryConfig",
    "RunOutcome",
    "RuntimeConfig",
    "Session",
    "SkillsConfig",
    "StorageConfig",
    "ToolSpec",
    "assemble",
    "build_host",
    "validate_config",
]
