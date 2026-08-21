"""LoopPlane host integration layer (feature 002-loopplane-host-interface).

A thin, public-safe seam for embedding and running the Phase-1 runtime
foundation from one configured entry point. It composes Phase-1 components
through their declared interfaces and adds no runtime internals of its own.

Typical use::

    from loopplane.host import LoopPlaneHost, RuntimeConfig, ToolSpec

    host = LoopPlaneHost(RuntimeConfig(model=model, tools=(ToolSpec(desc, fn),)))
    outcome = await host.run("please echo hello", on_event=my_sink)
"""

from loopplane.fairness import (
    PlatformFairness,
    PlatformFairnessPolicy,
    PlatformFairnessRejected,
)
from loopplane.host.assembly import AssembledRuntime, assemble
from loopplane.host.audit import TurnAuditEntry, checkpoint_records_to_audit_entries
from loopplane.host.capabilities import AllowedWorkspaceContextProvider
from loopplane.host.config import (
    ApprovalPolicy,
    CapabilityManagementConfig,
    ConfigError,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
    StorageConfig,
    ToolSpec,
    validate_config,
)
from loopplane.host.generation_validation import (
    GenerationExpectation,
    GenerationValidationResult,
    validate_active_generation,
)
from loopplane.host.host import (
    ApprovalDecision,
    LoopPlaneHost,
    Prompt,
    RunOutcome,
    Session,
    build_host,
)
from loopplane.host.snapshot import (
    DesktopActiveGenerationProvider,
    DesktopPortableSnapshotProvider,
    DesktopRuntimeStorageInitializer,
    PortableSnapshotResult,
    PortableSnapshotUnavailable,
    UnavailablePortableSnapshotProvider,
)
from loopplane.host.storage_authority import (
    DesktopStorageAuthorityFactory,
    StorageAuthorityFactory,
    StorageAuthorityLease,
)
from loopplane.model import ContentBlock, DocumentBlock, ImageBlock, TextBlock

__all__ = [
    "AllowedWorkspaceContextProvider",
    "ApprovalDecision",
    "ApprovalPolicy",
    "AssembledRuntime",
    "CapabilityManagementConfig",
    "ConfigError",
    "ContentBlock",
    "DesktopActiveGenerationProvider",
    "DesktopPortableSnapshotProvider",
    "DesktopRuntimeStorageInitializer",
    "DesktopStorageAuthorityFactory",
    "DocumentBlock",
    "GenerationExpectation",
    "GenerationValidationResult",
    "ImageBlock",
    "LoopPlaneHost",
    "MemoryConfig",
    "PlatformFairness",
    "PlatformFairnessPolicy",
    "PlatformFairnessRejected",
    "Prompt",
    "RunOutcome",
    "RuntimeConfig",
    "Session",
    "SkillsConfig",
    "StorageAuthorityFactory",
    "StorageAuthorityLease",
    "StorageConfig",
    "TextBlock",
    "ToolSpec",
    "TurnAuditEntry",
    "PortableSnapshotResult",
    "PortableSnapshotUnavailable",
    "UnavailablePortableSnapshotProvider",
    "assemble",
    "build_host",
    "checkpoint_records_to_audit_entries",
    "validate_active_generation",
    "validate_config",
]
