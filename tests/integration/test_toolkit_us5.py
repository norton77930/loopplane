"""US5: version packages and diagnose the catalog (spec US5; SC-008/009)."""

from __future__ import annotations

import pytest

from loopplane.toolkit import (
    ToolkitError,
    ToolPackage,
    Version,
    diagnose,
    discover,
    parse_version,
    select_by_policy,
)
from tests.toolkit_helpers import ScriptedToolAdapter, tool_descriptor


def test_parse_version() -> None:
    assert parse_version("1.2.3") == Version(1, 2, 3)


def test_parse_version_malformed_raises() -> None:
    for bad in ["1.2", "1.2.x", "1.2.3.4", "", "a.b.c", "1.2.-1"]:
        with pytest.raises(ToolkitError):
            parse_version(bad)


def test_version_order_is_total_and_numeric() -> None:
    assert Version(1, 0, 0) < Version(1, 1, 0) < Version(2, 0, 0)
    assert parse_version("1.10.0") > parse_version("1.9.0")


def test_select_by_policy_picks_highest() -> None:
    packages = [
        ToolPackage("p", "1.0.0"),
        ToolPackage("p", "2.3.1"),
        ToolPackage("p", "2.0.0"),
    ]
    chosen = select_by_policy(packages)
    assert chosen is not None and chosen.version == "2.3.1"
    assert select_by_policy([]) is None


def test_diagnose_reports_collision_schema_and_describe_failure() -> None:
    fs = ScriptedToolAdapter([tool_descriptor("shared", source="fs")])
    net = ScriptedToolAdapter([tool_descriptor("shared", source="net")])
    no_schema = ScriptedToolAdapter(
        [tool_descriptor("noschema", source="s", input_schema={})]
    )
    raising = ScriptedToolAdapter(raising=True)
    report = diagnose(discover([fs, net, no_schema, raising]))
    kinds = {d.kind for d in report.findings}
    assert {"name_collision", "missing_schema", "describe_failed"} <= kinds
    assert not report.ok()


def test_diagnose_clean_catalog_is_ok() -> None:
    adapter = ScriptedToolAdapter(
        [tool_descriptor("solo", source="s", input_schema={"type": "object"})]
    )
    assert diagnose(discover([adapter])).ok()
