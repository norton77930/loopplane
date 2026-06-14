"""Plugin discovery: scan host-supplied roots for plugin directories and parse
each ``plugin.json`` (spec FR-001, FR-008, FR-009, FR-010; data-model.md).

Discovery never raises: a missing, unreadable, unparseable, or credential-bearing
manifest yields a ``DiscoveredPlugin`` with ``manifest=None`` and a public-safe
``problem`` — the whole plugin is skipped, never partially loaded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from loopplane.plugins.manifest import PluginManifest, parse_manifest

# High-signal credential markers. A manifest is data only; if one of these appears
# in it, the plugin is treated as a public-safety failure and skipped (FR-010).
_CREDENTIAL_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "api-key",
    "password",
    "authorization",
    "bearer ",
    "client_secret",
    "private key",
    "sk-",
    "ghp_",
)


@dataclass(frozen=True)
class DiscoveredPlugin:
    """One candidate directory: its manifest, or ``None`` plus a public-safe reason."""

    directory: Path
    manifest: PluginManifest | None
    problem: str | None = None


def _credential_reason(raw: bytes) -> str | None:
    text = raw.decode("utf-8", errors="replace").lower()
    for marker in _CREDENTIAL_MARKERS:
        if marker in text:
            return "manifest appears to embed a credential and was skipped"
    return None


def discover(roots: Sequence[Path]) -> list[DiscoveredPlugin]:
    """Discover plugins under ``roots`` (broadest-first). Never raises (FR-009)."""
    found: list[DiscoveredPlugin] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            subdirs = sorted(p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue  # an unreadable root is skipped, discovery continues
        for directory in subdirs:
            manifest_path = directory / "plugin.json"
            if not manifest_path.is_file():
                continue  # not a plugin
            try:
                raw = manifest_path.read_bytes()
            except OSError:
                found.append(
                    DiscoveredPlugin(
                        directory, None, f"{directory.name}: manifest unreadable"
                    )
                )
                continue
            credential = _credential_reason(raw)
            if credential is not None:
                found.append(
                    DiscoveredPlugin(directory, None, f"{directory.name}: {credential}")
                )
                continue
            try:
                manifest = parse_manifest(raw)
            except ValidationError:
                found.append(
                    DiscoveredPlugin(
                        directory, None, f"{directory.name}: manifest invalid"
                    )
                )
                continue
            found.append(DiscoveredPlugin(directory, manifest, None))
    return found
