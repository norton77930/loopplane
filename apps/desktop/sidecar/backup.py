"""Backup disclosure and canonical archive composition (078 T069/T076)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .archive import create_portable_archive
except ImportError:  # pragma: no cover - script-path sidecar loading
    from archive import create_portable_archive  # type: ignore[no-redef]

DISCLOSURE = (
    "This backup is unencrypted (not application-encrypted). "
    "It preserves authorized conversation history and eligible Gateway artifacts, "
    "which can contain sensitive user, model, or tool-produced content. "
    "It excludes unsent drafts, device-private bindings, credentials, private "
    "configuration, arbitrary workspace contents, and process state."
)

EXCLUSIONS = (
    "unsent_drafts",
    "device_private_bindings",
    "profile_owner_lock",
    "capability_private_config",
    "credentials",
    "workspace_contents",
    "process_state",
)


@dataclass(frozen=True)
class BackupDescribe:
    disclosure: str
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    format: str
    schema_version: int = 1

    def to_public(self) -> dict[str, Any]:
        return {
            "disclosure": self.disclosure,
            "includes": list(self.includes),
            "excludes": list(self.excludes),
            "format": self.format,
            "schema_version": self.schema_version,
        }


def describe_backup() -> BackupDescribe:
    return BackupDescribe(
        disclosure=DISCLOSURE,
        includes=(
            "profile_portable_json",
            "projects_and_safe_preferences",
            "session_checkpoints",
            "eligible_referenced_gateway_artifacts",
        ),
        excludes=EXCLUSIONS,
        format="loopplane.desktop.backup",
    )


def create_backup_archive(
    destination: Path,
    *,
    profile_portable: dict[str, Any],
    snapshot_root: Path,
) -> dict[str, Any]:
    """Create the canonical archive after a successful Host snapshot only."""

    return create_portable_archive(
        destination,
        profile_portable=profile_portable,
        snapshot_root=snapshot_root,
        disclosure_acknowledged=True,
    )
