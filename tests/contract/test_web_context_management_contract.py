"""075 foundation contracts for MCP and workspace context management."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import allow_all, build_test_host, make_client  # noqa: E402


def test_mcp_and_workspace_context_lists_exist(tmp_path: Path) -> None:
    host = build_test_host(tmp_path)
    client = make_client(create_app(host, authenticator=allow_all))

    mcp = client.get("/v1/capabilities/mcp")
    contexts = client.get("/v1/capabilities/contexts")

    assert mcp.status_code == 200
    assert contexts.status_code == 200
    assert mcp.json() == []
    assert contexts.json() == []
