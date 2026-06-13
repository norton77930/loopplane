"""US4: inspect what a tool or package can do without invoking it (SC-005)."""

from __future__ import annotations

from loopplane.toolkit import DiscoveredTool, ToolPackage, build_manifest


def _tool(
    name: str = "n",
    *,
    source: str = "s",
    read_only: bool = False,
    concurrency_safe: bool = False,
) -> DiscoveredTool:
    return DiscoveredTool(
        source=source,
        name=name,
        description="d",
        read_only=read_only,
        concurrency_safe=concurrency_safe,
        input_schema={},
    )


def test_build_manifest_reflects_identity_and_package() -> None:
    tool = _tool(name="reader", source="fs", read_only=True, concurrency_safe=True)
    package = ToolPackage(name="pkg", version="1.2.0", capability_tags=("io", "safe"))
    manifest = build_manifest(tool, package)
    assert manifest.tool_name == "reader"
    assert manifest.source == "fs"
    assert manifest.read_only is True
    assert manifest.concurrency_safe is True
    assert (manifest.package, manifest.package_version) == ("pkg", "1.2.0")
    assert manifest.tags == ("io", "safe")


def test_build_manifest_is_deterministic() -> None:
    tool = _tool(name="t")
    package = ToolPackage("p", "1.0.0", capability_tags=("x",))
    assert build_manifest(tool, package) == build_manifest(tool, package)
