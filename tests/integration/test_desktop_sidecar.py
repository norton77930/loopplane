"""The desktop sidecar bridge streams a run over stdio (T002; FR-001/FR-002, SC-001).

The bridge lives under ``apps/desktop/sidecar/`` (the desktop app, not the
``loopplane`` package); it is loaded by file path so it is neither in the wheel nor a
new package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests.cli_helpers import scripted_host

pytestmark = pytest.mark.anyio

_BRIDGE_PATH = (
    Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar" / "bridge.py"
)


def _load_bridge() -> ModuleType:
    spec = importlib.util.spec_from_file_location("desktop_bridge", _BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge()


async def test_collect_events_streams_a_run() -> None:
    host = scripted_host("hi there")
    lines = await bridge.collect_events(host, "hello")
    assert any('"assistant-output-increment"' in line for line in lines)
    assert any('"hi there"' in line for line in lines)
    assert "outcome" in lines[-1]  # the terminal outcome is the final line


async def test_serve_drives_a_run_and_writes_an_outcome() -> None:
    host = scripted_host("done")
    pending: list[str | None] = ['{"op": "run", "prompt": "hello"}', None]

    async def read_line() -> str | None:
        return pending.pop(0) if pending else None

    out: list[str] = []
    await bridge.serve(host, read_line, out.append)
    assert any('"assistant-output-increment"' in line for line in out)
    assert any('"op": "outcome"' in line for line in out)


async def test_serve_reports_a_malformed_request() -> None:
    host = scripted_host("x")
    pending: list[str | None] = ["not json", None]

    async def read_line() -> str | None:
        return pending.pop(0) if pending else None

    out: list[str] = []
    await bridge.serve(host, read_line, out.append)
    assert any('"op": "error"' in line for line in out)
