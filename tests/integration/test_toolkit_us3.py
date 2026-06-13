"""US3: tool plugins registered through the gateway (spec US3; SC-005/007)."""

from __future__ import annotations

from loopplane.toolkit import ToolPackage, ToolPlugin, register_plugin
from tests.toolkit_helpers import (
    RecordingRegistrar,
    ScriptedToolAdapter,
    tool_descriptor,
)


def test_register_plugin_registers_each_adapter_once_in_order() -> None:
    first = ScriptedToolAdapter([tool_descriptor("a", source="s")])
    second = ScriptedToolAdapter([tool_descriptor("b", source="s")])
    plugin = ToolPlugin(
        name="pkg",
        package=ToolPackage(name="pkg", version="1.0.0"),
        adapters=(first, second),
    )
    registrar = RecordingRegistrar()
    register_plugin(plugin, registrar)
    assert registrar.registered == [first, second]


def test_register_plugin_never_invokes_a_tool() -> None:
    adapter = ScriptedToolAdapter([tool_descriptor("a", source="s")])
    plugin = ToolPlugin(
        name="p", package=ToolPackage("p", "1.0.0"), adapters=(adapter,)
    )
    # ScriptedToolAdapter.invoke raises; register_plugin must not call it.
    register_plugin(plugin, RecordingRegistrar())


def test_tool_package_carries_metadata() -> None:
    package = ToolPackage(
        name="pkg",
        version="2.1.0",
        description="d",
        source="src",
        capability_tags=("net",),
    )
    assert (package.name, package.version, package.capability_tags) == (
        "pkg",
        "2.1.0",
        ("net",),
    )
