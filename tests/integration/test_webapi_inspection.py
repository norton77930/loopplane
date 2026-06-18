"""Unit 027: read-only, metadata-only inspection endpoints over the web/API host.

Each endpoint is auth-gated, returns metadata only, executes no tool, and degrades to an
empty result when the underlying layer is absent. In-process only (no network).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.context import RunContext  # noqa: E402
from loopplane.host import ToolSpec  # noqa: E402
from loopplane.model import OutputBlock, ToolDescriptor  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    allow_all,
    build_test_host,
    deny_all,
    make_client,
    multi_text_model,
)


def _exploding_tool() -> ToolSpec:
    """A tool whose handler raises if executed during read-only inspection."""

    descriptor = ToolDescriptor(
        name="boom", description="never run me during inspection", input_schema={}
    )

    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        raise AssertionError("a tool was executed during read-only inspection")

    return ToolSpec(descriptor=descriptor, handler=handler)


def test_inspect_tools_lists_metadata_without_executing(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path, model=multi_text_model("a"), tools=(_exploding_tool(),)
    )
    client = make_client(create_app(host, authenticator=allow_all))

    response = client.get("/v1/inspect/tools")
    assert response.status_code == 200
    tools = response.json()
    assert {t["name"] for t in tools} == {"boom"}
    # metadata-only shape — no input/handler/raw fields
    assert all(set(t) == {"name", "description", "read_only", "source"} for t in tools)
    # inspection created no run/session (it executed nothing)
    assert client.get("/v1/sessions").json() == []


def test_inspect_skills_empty_state(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"))
    client = make_client(create_app(host, authenticator=allow_all))

    response = client.get("/v1/inspect/skills")
    assert response.status_code == 200
    assert response.json() == {"skills": [], "problems": []}


def test_inspect_mcp_and_memory_empty_states(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"))
    client = make_client(create_app(host, authenticator=allow_all))

    assert client.get("/v1/inspect/mcp").json() == []
    assert client.get("/v1/inspect/memory").json() == []
    assert client.get("/v1/inspect/memory", params={"q": "anything"}).json() == []


def test_inspection_is_auth_gated(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"))
    client = make_client(create_app(host, authenticator=deny_all))

    for path in (
        "/v1/inspect/skills",
        "/v1/inspect/tools",
        "/v1/inspect/mcp",
        "/v1/inspect/memory",
    ):
        assert client.get(path).status_code == 401, path
