"""075 web/API integration for MCP and workspace-context management."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

import loopplane.host.capability_manager as capability_manager_module
from loopplane.adapters.mcp import MCPServerConfig
from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput

pytest.importorskip("fastapi")

from loopplane.host import (  # noqa: E402
    AllowedWorkspaceContextProvider,
    CapabilityManagementConfig,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.host.capabilities import WorkspaceContext  # noqa: E402
from loopplane.model import TextBlock, ToolDescriptor  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.auth import Principal  # noqa: E402
from tests.webapi_helpers import make_client, text_model  # noqa: E402


async def principal_from_header(credential: str | None) -> Principal | None:
    if credential is None:
        return Principal(id="owner")
    scheme, _, subject = credential.partition(" ")
    if scheme.lower() != "bearer" or not subject:
        return None
    return Principal(id=subject)


def _host(
    tmp_path: Path,
    *,
    mutations_enabled: bool = True,
    runtime_activation_enabled: bool = False,
    allowed_context_provider: AllowedWorkspaceContextProvider | None = None,
) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=mutations_enabled,
                runtime_activation_enabled=runtime_activation_enabled,
                mcp_endpoint_policy=lambda *_args: True,
                allowed_context_provider=allowed_context_provider,
            ),
        ),
        working_scope=tmp_path,
    )


class _FakeMcpAdapter:
    def __init__(self, configs: Sequence[MCPServerConfig]) -> None:
        [self.config] = configs

    @property
    def connection_failures(self) -> dict[str, str]:
        return {}

    async def connect(self) -> None:
        return None

    def describe(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=f"{self.config.name}:lookup",
                description="managed lookup",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        ]

    async def invoke(
        self,
        name: str,
        call_input: dict[str, object],
        context: RunContext,
    ) -> AsyncIterator[AdapterOutput]:
        yield TextBlock(text="managed result")

    async def shutdown(self) -> None:
        return None


def test_mcp_and_context_management_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capability_manager_module,
        "MCPToolAdapter",
        _FakeMcpAdapter,
        raising=False,
    )
    client = make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    )

    mcp = client.post(
        "/v1/capabilities/mcp",
        json={
            "name": "docs",
            "transport": "http",
            "url": "https://mcp.example.invalid",
        },
    )

    assert mcp.status_code == 200
    assert mcp.json()["result"]["resource_id"] == "docs"
    [config] = client.get("/v1/capabilities/mcp").json()
    assert config["name"] == "docs"
    assert config["transport"] == "http"
    detail = client.get("/v1/capabilities/mcp/docs")
    assert detail.status_code == 200
    assert detail.json()["name"] == "docs"

    reconnect = client.post("/v1/capabilities/mcp/docs/reconnect")
    assert reconnect.status_code == 200
    assert reconnect.json()["ok"] is True
    assert reconnect.json()["status"] == "connected"

    stdio = client.post(
        "/v1/capabilities/mcp",
        json={
            "name": "local",
            "transport": "stdio",
            "command": "private-command",
            "args": ["private-arg"],
        },
    )
    assert stdio.status_code == 200
    assert stdio.json()["result"]["status"] == "invalid"

    context = client.post(
        "/v1/capabilities/contexts",
        json={
            "name": "Docs",
            "description": "documentation workspace",
            "workspace_label": "docs-repo",
        },
    )

    assert context.status_code == 200
    assert context.json()["context"]["workspace_label"] == "docs-repo"
    assert (
        client.get("/v1/capabilities/contexts/Docs").json()["description"]
        == "documentation workspace"
    )

    other = {"Authorization": "Bearer other"}
    assert client.get("/v1/capabilities/mcp", headers=other).json() == []
    non_owner = client.get("/v1/capabilities/mcp/docs", headers=other)
    unknown = client.get("/v1/capabilities/mcp/missing")
    assert non_owner.status_code == unknown.status_code == 404
    assert non_owner.json() == unknown.json()

    assert client.delete("/v1/capabilities/mcp/docs", params={"confirm": True}).json()[
        "ok"
    ]


@pytest.mark.parametrize(
    ("mutations_enabled", "runtime_activation_enabled"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_mcp_gate_matrix_keeps_mutation_and_runtime_authority_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutations_enabled: bool,
    runtime_activation_enabled: bool,
) -> None:
    monkeypatch.setattr(
        capability_manager_module,
        "MCPToolAdapter",
        _FakeMcpAdapter,
        raising=False,
    )
    host = _host(
        tmp_path,
        mutations_enabled=mutations_enabled,
        runtime_activation_enabled=runtime_activation_enabled,
    )
    with make_client(create_app(host, authenticator=principal_from_header)) as client:
        saved = client.post(
            "/v1/capabilities/mcp",
            json={
                "name": "docs",
                "transport": "http",
                "url": "https://mcp.example.invalid",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["result"]["ok"] is mutations_enabled

        listed = client.get("/v1/capabilities/mcp").json()
        if not mutations_enabled:
            assert listed == []
            assert host._assembled.gateway.descriptors("owner") == []
            return

        assert [entry["id"] for entry in listed] == ["docs"]
        reconnected = client.post("/v1/capabilities/mcp/docs/reconnect")
        assert reconnected.status_code == 200
        assert reconnected.json()["ok"] is True
        names = {
            descriptor.name
            for descriptor in host._assembled.gateway.descriptors("owner")
        }
        assert ("docs:lookup" in names) is runtime_activation_enabled

        deleted = client.delete("/v1/capabilities/mcp/docs", params={"confirm": True})
        assert deleted.status_code == 200
        assert deleted.json()["ok"] is True
        assert host._assembled.gateway.descriptors("owner") == []


def test_session_context_binding_is_owner_scoped(tmp_path: Path) -> None:
    with make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    ) as client:
        context = client.post(
            "/v1/capabilities/contexts",
            json={
                "name": "Docs",
                "description": "documentation workspace",
                "workspace_label": "docs-repo",
            },
        )
        session_id = client.post("/v1/sessions").json()["session_id"]

        bound = client.post(
            f"/v1/sessions/{session_id}/context",
            json={"context_id": context.json()["context"]["id"]},
        )

        assert bound.status_code == 200
        assert bound.json()["context_id"] == "Docs"
        [summary] = client.get("/v1/sessions").json()
        assert summary["context_id"] == "Docs"
        assert summary["context_name"] == "Docs"

        denied = client.post(
            f"/v1/sessions/{session_id}/context",
            headers={"Authorization": "Bearer other"},
            json={"context_id": "Docs"},
        )
        assert denied.status_code == 404
        assert (
            client.get(
                "/v1/capabilities/contexts",
                headers={"Authorization": "Bearer other"},
            ).json()
            == []
        )


def test_allowed_workspace_context_is_safe_bindable_and_non_disclosing(
    tmp_path: Path,
) -> None:
    def provider(principal_id: str) -> Sequence[WorkspaceContext]:
        if principal_id != "owner":
            return ()
        return (
            WorkspaceContext(
                id="shared-docs",
                name="Shared Docs",
                description="approved documentation",
                workspace_label="shared-repo",
                owner_id="private-owner",
                scope="owned",
                actions=("delete",),
                problem="private provider detail",
            ),
        )

    with make_client(
        create_app(
            _host(tmp_path, allowed_context_provider=provider),
            authenticator=principal_from_header,
        )
    ) as client:
        [context] = client.get("/v1/capabilities/contexts").json()
        assert context["id"] == "shared-docs"
        assert context["scope"] == "shared_read_only"
        assert context["status"] == "read_only"
        assert "owner_id" not in context
        assert context["problem"] is None
        assert context["actions"] == ["open", "bind"]

        detail = client.get("/v1/capabilities/contexts/shared-docs")
        assert detail.status_code == 200
        assert "private-owner" not in detail.text
        assert "private provider detail" not in detail.text

        session_id = client.post("/v1/sessions").json()["session_id"]
        bound = client.post(
            f"/v1/sessions/{session_id}/context",
            json={"context_id": "shared-docs"},
        )
        assert bound.status_code == 200
        assert bound.json()["context_id"] == "shared-docs"

        other = {"Authorization": "Bearer other"}
        assert client.get("/v1/capabilities/contexts", headers=other).json() == []
        hidden = client.get(
            "/v1/capabilities/contexts/shared-docs",
            headers=other,
        )
        unknown = client.get("/v1/capabilities/contexts/missing", headers=other)
        assert hidden.status_code == unknown.status_code == 404
        assert hidden.json() == unknown.json()
        denied = client.post(
            f"/v1/sessions/{session_id}/context",
            headers=other,
            json={"context_id": "shared-docs"},
        )
        assert denied.status_code == 404


@pytest.mark.parametrize(
    ("mutations_enabled", "runtime_activation_enabled"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_allowed_context_gate_matrix_is_action_driven_and_not_persisted(
    tmp_path: Path,
    mutations_enabled: bool,
    runtime_activation_enabled: bool,
) -> None:
    def provider(principal_id: str) -> Sequence[WorkspaceContext]:
        if principal_id != "owner":
            return ()
        return (
            WorkspaceContext(
                id="shared-docs",
                name="Shared Docs",
                description="approved documentation",
                workspace_label="shared-repo",
            ),
        )

    with make_client(
        create_app(
            _host(
                tmp_path,
                mutations_enabled=mutations_enabled,
                runtime_activation_enabled=runtime_activation_enabled,
                allowed_context_provider=provider,
            ),
            authenticator=principal_from_header,
        )
    ) as client:
        [context] = client.get("/v1/capabilities/contexts").json()
        assert context["actions"] == (
            ["open", "bind"] if mutations_enabled else ["open"]
        )
        assert client.get("/v1/capabilities/contexts/shared-docs").status_code == 200

        session_id = client.post("/v1/sessions").json()["session_id"]
        bound = client.post(
            f"/v1/sessions/{session_id}/context",
            json={"context_id": "shared-docs"},
        )
        assert bound.status_code == (200 if mutations_enabled else 404)

    with make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    ) as restarted:
        assert restarted.get("/v1/capabilities/contexts").json() == []


def test_workspace_context_and_binding_survive_host_restart(tmp_path: Path) -> None:
    with make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    ) as client:
        created = client.post(
            "/v1/capabilities/contexts",
            json={
                "name": "Docs",
                "description": "documentation workspace",
                "workspace_label": "docs-repo",
            },
        )
        session_id = client.post("/v1/sessions").json()["session_id"]
        bound = client.post(
            f"/v1/sessions/{session_id}/context",
            json={"context_id": created.json()["context"]["id"]},
        )
        assert bound.status_code == 200

    with make_client(
        create_app(_host(tmp_path), authenticator=principal_from_header)
    ) as restarted:
        [context] = restarted.get("/v1/capabilities/contexts").json()
        assert context["id"] == "Docs"
        [summary] = restarted.get("/v1/sessions").json()
        assert summary["context_id"] == "Docs"
        assert summary["context_workspace_label"] == "docs-repo"

        other = {"Authorization": "Bearer other"}
        assert (
            restarted.get(
                "/v1/capabilities/contexts",
                headers=other,
            ).json()
            == []
        )
        non_owner = restarted.get(
            "/v1/capabilities/contexts/Docs",
            headers=other,
        )
        unknown = restarted.get("/v1/capabilities/contexts/missing")
        assert non_owner.status_code == unknown.status_code == 404
        assert non_owner.json() == unknown.json()
