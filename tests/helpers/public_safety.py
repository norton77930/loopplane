"""Synthetic public-safety markers for 078 Desktop (T010).

Distinguishes **content surfaces** (authorized conversation / eligible artifacts,
which may losslessly retain sensitive user/model/tool text) from **secondary
surfaces** (status, audit metadata, RPC errors, logs, manifests) where
LoopPlane-owned secrets, private paths, rules, PIDs, and raw errors must never
appear.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Synthetic markers (must not appear as real product defaults)
# ---------------------------------------------------------------------------

LOOPPLANE_SECRET_MARKER: Final[str] = "lp-synth-secret-TOKEN-9f3c2a1b"
LOOPPLANE_PATH_MARKER: Final[str] = r"C:\Users\lp-synth\private\workspace\secret-dir"
LOOPPLANE_RULE_MARKER: Final[str] = "lp-synth-private-rule:deny-everything"
LOOPPLANE_PID_MARKER: Final[str] = "lp-synth-pid=424242"
LOOPPLANE_RAW_ERROR_MARKER: Final[str] = (
    "Traceback (most recent call last):\n  lp-synth-internal-stack"
)

AUTHORIZED_USER_CONTENT_MARKER: Final[str] = (
    "user said: keep my API key sk-synth-user-content-ok"
)
AUTHORIZED_MODEL_CONTENT_MARKER: Final[str] = (
    "model wrote: path excerpt /home/user/project/file.ts"
)
AUTHORIZED_TOOL_CONTENT_MARKER: Final[str] = (
    "tool output: wrote C:\\Users\\lp-synth\\private\\workspace\\out.txt"
)
AUTHORIZED_ARTIFACT_MARKER: Final[str] = "artifact-body:lp-synth-eligible-blob"

SECONDARY_SURFACE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "audit",
        "rpc_error",
        "log",
        "manifest",
        "backup_manifest",
        "diagnostic",
    }
)

CONTENT_SURFACE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "conversation",
        "eligible_artifact",
    }
)


@dataclass(frozen=True, slots=True)
class SurfacePayload:
    """A rendered or serialized payload with an explicit surface kind."""

    kind: str
    text: str


def all_prohibited_secondary_markers() -> tuple[str, ...]:
    return (
        LOOPPLANE_SECRET_MARKER,
        LOOPPLANE_PATH_MARKER,
        LOOPPLANE_RULE_MARKER,
        LOOPPLANE_PID_MARKER,
        LOOPPLANE_RAW_ERROR_MARKER,
    )


def all_authorized_content_markers() -> tuple[str, ...]:
    return (
        AUTHORIZED_USER_CONTENT_MARKER,
        AUTHORIZED_MODEL_CONTENT_MARKER,
        AUTHORIZED_TOOL_CONTENT_MARKER,
        AUTHORIZED_ARTIFACT_MARKER,
    )


def assert_secondary_surface_clean(payload: SurfacePayload) -> None:
    """Fail if a secondary surface discloses prohibited markers."""

    if payload.kind not in SECONDARY_SURFACE_KINDS:
        raise AssertionError(
            "assert_secondary_surface_clean requires secondary kind, "
            f"got {payload.kind!r}"
        )
    for marker in all_prohibited_secondary_markers():
        if marker in payload.text:
            raise AssertionError(
                f"secondary surface {payload.kind!r} leaked marker {marker!r}"
            )


def assert_content_surface_may_retain(payload: SurfacePayload, marker: str) -> None:
    """Content surfaces may retain authorized (possibly sensitive) markers."""

    if payload.kind not in CONTENT_SURFACE_KINDS:
        raise AssertionError(
            "assert_content_surface_may_retain requires content kind, "
            f"got {payload.kind!r}"
        )
    if marker not in payload.text:
        raise AssertionError(
            f"content surface {payload.kind!r} missing expected marker {marker!r}"
        )


def scan_secondary_surfaces(payloads: Iterable[SurfacePayload]) -> list[str]:
    """Return human-readable leak findings for secondary surfaces only."""

    findings: list[str] = []
    for payload in payloads:
        if payload.kind not in SECONDARY_SURFACE_KINDS:
            continue
        for marker in all_prohibited_secondary_markers():
            if marker in payload.text:
                findings.append(f"{payload.kind}: leaked {marker!r}")
    return findings
