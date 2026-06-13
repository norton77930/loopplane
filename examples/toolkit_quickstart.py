"""Runnable example: organize a tool ecosystem above the Tool Gateway.

Public-safe and credential-free. Scripted tool sources are discovered into a
catalog, a capability manifest is derived, the catalog is diagnosed, a version is
selected, and a plugin is registered through a recording registrar — no tool is
ever invoked (the gateway keeps execution; Constitution V).

Run::

    python examples/toolkit_quickstart.py
"""

from __future__ import annotations

from collections.abc import Sequence

from loopplane.model import ToolDescriptor
from loopplane.toolkit import (
    ToolPackage,
    ToolPlugin,
    build_manifest,
    diagnose,
    discover,
    register_plugin,
    select_by_policy,
)


class _ScriptedAdapter:
    """An in-process ToolAdapter; invoke raises so the toolkit never executes."""

    def __init__(self, descriptors: Sequence[ToolDescriptor]) -> None:
        self._descriptors = tuple(descriptors)

    def describe(self) -> Sequence[ToolDescriptor]:
        return self._descriptors

    def invoke(
        self, name: str, call_input: dict[str, object], context: object
    ) -> object:
        raise AssertionError("the toolkit layer must not invoke tools")

    async def shutdown(self) -> None:
        return None


class _RecordingRegistrar:
    def __init__(self) -> None:
        self.registered: list[object] = []

    def register_adapter(self, adapter: object) -> None:
        self.registered.append(adapter)


def _descriptor(name: str, *, source: str, read_only: bool = False) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=f"the {name} tool",
        input_schema={"type": "object"},
        concurrency_safe=False,
        read_only=read_only,
        source=source,
    )


def run_demo() -> None:
    fs = _ScriptedAdapter(
        [
            _descriptor("read_file", source="fs", read_only=True),
            _descriptor("write_file", source="fs"),
        ]
    )
    net = _ScriptedAdapter([_descriptor("fetch_url", source="net", read_only=True)])

    catalog = discover([fs, net])
    print("Catalog:")
    for tool in catalog.tools:
        print(f"  [{tool.source}] {tool.name} (read_only={tool.read_only})")
    print(f"collisions: {catalog.collisions()}; failed: {catalog.failed_sources}")

    package = ToolPackage(
        name="fs-tools", version="1.3.0", capability_tags=("filesystem",)
    )
    manifest = build_manifest(catalog.tools[0], package)
    print(
        f"\nManifest {manifest.tool_name}: read_only={manifest.read_only}, "
        f"package={manifest.package} v{manifest.package_version}, tags={manifest.tags}"
    )

    report = diagnose(catalog)
    findings = [(d.kind, d.subject) for d in report.findings]
    print(f"Diagnostics ok={report.ok()} findings={findings}")

    chosen = select_by_policy(
        [ToolPackage("fs-tools", "1.3.0"), ToolPackage("fs-tools", "1.4.2")]
    )
    print(f"selected version: {chosen.version if chosen else None}")

    registrar = _RecordingRegistrar()
    register_plugin(
        ToolPlugin(name="fs-tools", package=package, adapters=(fs,)), registrar
    )
    print(
        f"\nregistered {len(registrar.registered)} adapter(s) "
        "(tools execute only through the gateway)"
    )


if __name__ == "__main__":
    run_demo()
