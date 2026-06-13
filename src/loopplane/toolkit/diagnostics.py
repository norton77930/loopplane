"""Catalog diagnostics (contracts/catalog.md; FR-050-FR-051).

``diagnose`` reads catalog data only — it never invokes a tool or probes liveness
— and returns ordered, public-safe findings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loopplane.toolkit.catalog import DiscoveredTool, ToolCatalog

DiagnosticKind = Literal[
    "describe_failed",
    "name_collision",
    "missing_schema",
    "malformed_schema",
    "capability_conflict",
]


@dataclass(frozen=True)
class Diagnostic:
    kind: DiagnosticKind
    subject: str
    detail: str


@dataclass(frozen=True)
class DiagnosticsReport:
    findings: tuple[Diagnostic, ...]

    def ok(self) -> bool:
        return not self.findings


def diagnose(catalog: ToolCatalog) -> DiagnosticsReport:
    """Report describe failures, name collisions, missing/malformed input schemas,
    and capability conflicts — read-only, never invoking a tool (FR-050, FR-051)."""

    findings: list[Diagnostic] = []

    for source in catalog.failed_sources:
        findings.append(
            Diagnostic(
                "describe_failed", source, "describe() raised; no tools discovered"
            )
        )

    by_name: dict[str, list[DiscoveredTool]] = {}
    for tool in catalog.tools:
        by_name.setdefault(tool.name, []).append(tool)

    for name, entries in by_name.items():
        if len(entries) >= 2:
            findings.append(
                Diagnostic("name_collision", name, "exposed by two or more sources")
            )
            if len({e.read_only for e in entries}) > 1 or (
                len({e.concurrency_safe for e in entries}) > 1
            ):
                findings.append(
                    Diagnostic(
                        "capability_conflict",
                        name,
                        "colliding tools declare different capabilities",
                    )
                )

    for tool in catalog.tools:
        schema = tool.input_schema
        if not isinstance(schema, Mapping):
            findings.append(
                Diagnostic(
                    "malformed_schema", tool.name, "input_schema is not a mapping"
                )
            )
        elif not schema:
            findings.append(
                Diagnostic("missing_schema", tool.name, "input_schema is empty")
            )

    findings.sort(key=lambda finding: (finding.kind, finding.subject))
    return DiagnosticsReport(findings=tuple(findings))
