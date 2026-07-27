"""075 capability-management unit coverage for memory and skills."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

import loopplane.host.capability_manager as capability_manager_module
from loopplane.adapters.mcp import MCPServerConfig
from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput
from loopplane.host import (
    CapabilityManagementConfig,
    ConfigError,
    LoopPlaneHost,
    MemoryConfig,
    RuntimeConfig,
    SkillsConfig,
    StorageConfig,
    validate_config,
)
from loopplane.host.capabilities import (
    AllowedWorkspaceContextProvider,
    ManagedSchedule,
    ManagedScheduleRunner,
    WorkspaceContext,
)
from loopplane.memory import MemoryEntry, MemoryStore
from loopplane.model import TextBlock, ToolDescriptor
from loopplane.skills import Skill
from tests.webapi_helpers import text_model


class _RecordingScheduleRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ManagedSchedule]] = []
        self.fail = False

    def run_now(self, principal_id: str, schedule: ManagedSchedule) -> None:
        if self.fail:
            raise RuntimeError("private-runner.invalid D:/private/scheduler")
        self.calls.append((principal_id, schedule))


def _host(
    tmp_path: Path,
    *,
    runtime_activation_enabled: bool = False,
    schedule_runner: ManagedScheduleRunner | None = None,
    allowed_context_provider: AllowedWorkspaceContextProvider | None = None,
) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            memory=MemoryConfig(source=tmp_path / "memory"),
            skills=SkillsConfig(sources=(tmp_path / "skills",)),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=runtime_activation_enabled,
                mcp_endpoint_policy=lambda *_args: True,
                schedule_runner=schedule_runner,
                allowed_context_provider=allowed_context_provider,
            ),
        ),
        working_scope=tmp_path,
    )


def test_capability_management_configuration_defaults_off() -> None:
    runtime = RuntimeConfig(model=text_model())

    assert runtime.capability_management is None

    configured = CapabilityManagementConfig()
    assert configured.mutations_enabled is False
    assert configured.runtime_activation_enabled is False
    assert configured.mcp_endpoint_policy is None
    assert configured.schedule_runner is None
    assert configured.allowed_context_provider is None


def test_capability_management_configuration_coerces_from_mapping() -> None:
    runtime = RuntimeConfig.from_mapping(
        {
            "model": text_model(),
            "capability_management": {
                "mutations_enabled": True,
                "runtime_activation_enabled": True,
            },
        }
    )

    assert runtime.capability_management == CapabilityManagementConfig(
        mutations_enabled=True,
        runtime_activation_enabled=True,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("mcp_endpoint_policy", object()),
        ("schedule_runner", object()),
        ("allowed_context_provider", object()),
    ],
)
def test_capability_management_configuration_validates_collaborators(
    field_name: str, value: object
) -> None:
    config = RuntimeConfig(
        model=text_model(),
        capability_management=CapabilityManagementConfig(**{field_name: value}),
    )

    with pytest.raises(ConfigError, match=field_name):
        validate_config(config)


def test_capability_mutations_are_disabled_by_default(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            memory=MemoryConfig(source=tmp_path / "memory"),
        ),
        working_scope=tmp_path,
    )

    result = host.write_managed_memory(
        name="pref",
        kind="user",
        description="editor preference",
        content="likes tabs",
        principal_id="owner",
    )

    assert result.ok is False
    assert result.status == "disabled_by_policy"
    assert host.list_managed_memory(principal_id="owner") == ()


def test_capability_mutation_without_storage_fails_unavailable(
    tmp_path: Path,
) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            memory=MemoryConfig(source=tmp_path / "memory"),
            capability_management=CapabilityManagementConfig(mutations_enabled=True),
        ),
        working_scope=tmp_path,
    )

    result = host.write_managed_memory(
        name="pref",
        kind="user",
        description="editor preference",
        content="likes tabs",
        principal_id="owner",
    )

    assert result.ok is False
    assert result.status == "unavailable"
    assert host.list_managed_memory(principal_id="owner") == ()


async def _discard(*_args: object) -> None:
    return None


class _FakeMcpAdapter:
    fail_connect = False
    instances: list[_FakeMcpAdapter] = []

    def __init__(self, configs: Sequence[MCPServerConfig]) -> None:
        [self.config] = configs
        self._failures: dict[str, str] = {}
        self.shutdown_calls = 0
        self.__class__.instances.append(self)

    @property
    def connection_failures(self) -> dict[str, str]:
        return dict(self._failures)

    async def connect(self) -> None:
        if self.fail_connect:
            self._failures[self.config.name] = (
                "RuntimeError: private-host.invalid D:/private/mcp"
            )

    def describe(self) -> list[ToolDescriptor]:
        if self._failures:
            return []
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
        yield TextBlock(text="managed mcp result")

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


def test_memory_management_write_get_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.write_managed_memory(
        name="pref",
        kind="user",
        description="editor preference",
        content="likes tabs",
    )

    assert written.ok is True
    assert written.resource_id == "pref"
    assert [entry.name for entry in host.list_managed_memory()] == ["pref"]
    assert host.get_managed_memory("pref").content == "likes tabs"

    deleted = host.delete_managed_memory("pref", confirm=True)

    assert deleted.ok is True
    assert host.list_managed_memory() == ()


def test_memory_is_owner_scoped_durable_and_shared_read_only(tmp_path: Path) -> None:
    shared_body = "shared guidance " + ("界" * 200)
    MemoryStore(tmp_path / "memory").write(
        MemoryEntry(
            type="project",
            name="host-guide",
            description="shared host guidance",
            body=shared_body,
        )
    )
    host = _host(tmp_path)

    assert host.write_managed_memory(
        name="pref",
        kind="user",
        description="owner preference",
        content="owner likes tabs",
        principal_id="owner",
    ).ok
    assert host.write_managed_memory(
        name="pref",
        kind="user",
        description="other preference",
        content="other likes spaces",
        principal_id="other",
    ).ok
    assert host.write_managed_memory(
        name="owner-only",
        kind="reference",
        description="private note",
        content="private owner content",
        principal_id="owner",
    ).ok

    owner = {
        entry.id: entry for entry in host.list_managed_memory(principal_id="owner")
    }
    other = {
        entry.id: entry for entry in host.list_managed_memory(principal_id="other")
    }
    assert set(owner) == {"host-guide", "owner-only", "pref"}
    assert set(other) == {"host-guide", "pref"}
    assert host.get_managed_memory("pref", principal_id="owner").content == (
        "owner likes tabs"
    )
    assert host.get_managed_memory("pref", principal_id="other").content == (
        "other likes spaces"
    )
    assert owner["host-guide"].scope == "shared_read_only"
    assert owner["host-guide"].actions == ("open",)
    assert owner["host-guide"].snippet == shared_body[:160]
    shared_detail = host.get_managed_memory("host-guide", principal_id="owner")
    assert shared_detail.content == ""
    assert shared_detail.snippet == shared_body[:160]
    assert owner["pref"].scope == "owned"
    assert set(owner["pref"].actions) == {"open", "update", "delete"}

    with pytest.raises(KeyError):
        host.get_managed_memory("owner-only", principal_id="other")
    refused = host.delete_managed_memory(
        "owner-only",
        confirm=True,
        principal_id="other",
    )
    assert refused.ok is False
    assert refused.status == "unavailable"
    assert host.get_managed_memory("owner-only", principal_id="owner").content == (
        "private owner content"
    )

    shared_write = host.write_managed_memory(
        name="host-guide",
        kind="project",
        description="overwrite",
        content="overwrite",
        principal_id="owner",
    )
    shared_delete = host.delete_managed_memory(
        "host-guide",
        confirm=True,
        principal_id="owner",
    )
    assert shared_write.status == shared_delete.status == "read_only"

    restarted = _host(tmp_path)
    assert restarted.get_managed_memory("pref", principal_id="owner").content == (
        "owner likes tabs"
    )
    assert restarted.get_managed_memory("pref", principal_id="other").content == (
        "other likes spaces"
    )


def test_skill_management_write_import_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.write_managed_skill(
        name="writer",
        description="writes notes",
        instructions="write concise notes",
    )

    assert written.ok is True
    assert [skill.name for skill in host.list_managed_skills()] == ["writer"]
    assert host.get_managed_skill("writer").instructions == "write concise notes"

    imported = host.import_managed_skill(
        {
            "name": "reviewer",
            "description": "reviews notes",
            "instructions": "review concise notes",
        }
    )

    assert imported.ok is True
    assert {skill.name for skill in host.list_managed_skills()} == {
        "reviewer",
        "writer",
    }

    deleted = host.delete_managed_skill("writer", confirm=True)

    assert deleted.ok is True
    assert [skill.name for skill in host.list_managed_skills()] == ["reviewer"]


def test_skills_are_owner_scoped_durable_and_shared_read_only(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "host-guide.json").write_text(
        Skill(
            name="host-guide",
            description="shared host guidance",
            instructions="follow the host guide",
        ).model_dump_json(),
        encoding="utf-8",
    )
    host = _host(tmp_path)

    assert host.write_managed_skill(
        name="writer",
        description="owner writer",
        instructions="write owner notes",
        principal_id="owner",
    ).ok
    assert host.write_managed_skill(
        name="writer",
        description="other writer",
        instructions="write other notes",
        principal_id="other",
    ).ok
    assert host.import_managed_skill(
        {
            "name": "reviewer",
            "description": "owner reviewer",
            "instructions": "review owner notes",
        },
        principal_id="owner",
    ).ok

    owner = {skill.id: skill for skill in host.list_managed_skills("owner")}
    other = {skill.id: skill for skill in host.list_managed_skills("other")}
    assert set(owner) == {"host-guide", "reviewer", "writer"}
    assert set(other) == {"host-guide", "writer"}
    assert owner["host-guide"].scope == "shared_read_only"
    assert owner["host-guide"].source == "host"
    assert owner["host-guide"].actions == ("open",)
    assert host.get_managed_skill("host-guide", principal_id="owner").instructions == ""
    assert owner["writer"].scope == "owned"
    assert set(owner["writer"].actions) == {"open", "update", "delete"}
    assert host.get_managed_skill("writer", principal_id="owner").instructions == (
        "write owner notes"
    )
    assert host.get_managed_skill("writer", principal_id="other").instructions == (
        "write other notes"
    )

    with pytest.raises(KeyError):
        host.get_managed_skill("reviewer", principal_id="other")
    refused = host.delete_managed_skill(
        "reviewer",
        confirm=True,
        principal_id="other",
    )
    assert refused.ok is False
    assert refused.status == "unavailable"
    assert host.get_managed_skill("reviewer", principal_id="owner").instructions == (
        "review owner notes"
    )

    shared_write = host.write_managed_skill(
        name="host-guide",
        description="overwrite",
        instructions="overwrite",
        principal_id="owner",
    )
    shared_delete = host.delete_managed_skill(
        "host-guide",
        confirm=True,
        principal_id="owner",
    )
    assert shared_write.status == shared_delete.status == "read_only"

    restarted = _host(tmp_path)
    assert (
        restarted.get_managed_skill(
            "writer",
            principal_id="owner",
        ).instructions
        == "write owner notes"
    )
    assert (
        restarted.get_managed_skill(
            "writer",
            principal_id="other",
        ).instructions
        == "write other notes"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("transport", "url"),
    [
        ("http", "https://user@example.invalid/mcp"),
        ("http", "https://example.invalid/mcp?mode=sample"),
        ("http", "https://example.invalid/mcp#section"),
        ("http", "https:///missing-host"),
        ("http", "wss://example.invalid/mcp"),
        ("sse", "https://example.invalid:invalid/mcp"),
        ("websocket", "https://example.invalid/mcp"),
    ],
)
async def test_mcp_structurally_unsafe_endpoints_do_not_persist_or_leak(
    tmp_path: Path,
    transport: str,
    url: str,
) -> None:
    host = _host(tmp_path)

    result = await host.upsert_managed_mcp(
        name="docs",
        transport=transport,
        url=url,
        principal_id="owner",
    )

    assert result.ok is False
    assert result.status == "invalid"
    assert result.message == "mcp configuration is invalid"
    assert url not in repr(result)
    assert host.list_managed_mcp("owner") == ()


@pytest.mark.anyio
async def test_mcp_default_deny_policy_and_stdio_refusal_do_not_persist(
    tmp_path: Path,
) -> None:
    no_policy = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "no-policy"),
            capability_management=CapabilityManagementConfig(mutations_enabled=True),
        ),
        working_scope=tmp_path,
    )
    denied = await no_policy.upsert_managed_mcp(
        name="docs",
        transport="http",
        url="https://mcp.example.invalid",
        principal_id="owner",
    )
    stdio = await no_policy.upsert_managed_mcp(
        name="local",
        transport="stdio",
        command="private-command",
        args=("private-arg",),
        principal_id="owner",
    )

    assert denied.ok is False
    assert denied.status == "invalid"
    assert stdio.ok is False
    assert stdio.status == "invalid"
    assert no_policy.list_managed_mcp("owner") == ()

    rejected = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "rejected"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                mcp_endpoint_policy=lambda *_args: False,
            ),
        ),
        working_scope=tmp_path,
    )
    result = await rejected.upsert_managed_mcp(
        name="docs",
        transport="sse",
        url="https://mcp.example.invalid",
        principal_id="owner",
    )
    assert result.ok is False
    assert rejected.list_managed_mcp("owner") == ()


@pytest.mark.anyio
async def test_mcp_management_upsert_reconnect_failure_and_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeMcpAdapter.fail_connect = False
    _FakeMcpAdapter.instances = []
    monkeypatch.setattr(
        capability_manager_module,
        "MCPToolAdapter",
        _FakeMcpAdapter,
        raising=False,
    )
    host = _host(tmp_path, runtime_activation_enabled=True)

    upserted = await host.upsert_managed_mcp(
        name="docs",
        transport="http",
        url="https://mcp.example.invalid",
        principal_id="owner",
    )

    assert upserted.ok is True
    assert upserted.resource_id == "docs"
    [config] = host.list_managed_mcp("owner")
    assert config.name == "docs"
    assert config.transport == "http"
    assert config.status == "disconnected"
    assert config.tool_count == 0

    reconnected = await host.reconnect_managed_mcp("docs", principal_id="owner")

    assert reconnected.ok is True
    assert reconnected.resource_id == "docs"
    [connected] = host.list_managed_mcp("owner")
    assert connected.status == "connected"
    assert connected.tools == ("docs:lookup",)

    restarted = _host(tmp_path)
    [durable] = restarted.list_managed_mcp("owner")
    assert durable.transport == "http"
    assert durable.status == "connected"

    _FakeMcpAdapter.fail_connect = True
    failed = await host.reconnect_managed_mcp("docs", principal_id="owner")
    assert failed.ok is False
    assert failed.status == "failed"
    assert failed.message == "mcp reconnect failed"
    [failed_config] = host.list_managed_mcp("owner")
    assert failed_config.problem == "connection unavailable"
    assert "private-host" not in repr((failed, failed_config))
    assert _FakeMcpAdapter.instances[-2].shutdown_calls == 1
    assert _FakeMcpAdapter.instances[-1].shutdown_calls == 1

    deleted = await host.delete_managed_mcp(
        "docs",
        confirm=True,
        principal_id="owner",
    )

    assert deleted.ok is True
    assert host.list_managed_mcp("owner") == ()


def test_allowed_workspace_contexts_are_principal_safe_projections(
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
                status="failed",
                owner_id="private-owner",
                scope="owned",
                actions=("delete",),
                problem="private provider failure",
            ),
        )

    host = _host(tmp_path, allowed_context_provider=provider)

    [shared] = host.list_workspace_contexts("owner")
    assert shared == WorkspaceContext(
        id="shared-docs",
        name="Shared Docs",
        description="approved documentation",
        workspace_label="shared-repo",
        status="read_only",
        owner_id=None,
        scope="shared_read_only",
        actions=("open", "bind"),
        problem=None,
    )
    assert host.get_workspace_context("shared-docs", principal_id="owner") == shared
    assert host.list_workspace_contexts("other") == ()
    with pytest.raises(KeyError):
        host.get_workspace_context("shared-docs", principal_id="other")


def test_allowed_workspace_context_collisions_and_provider_failures_fail_closed(
    tmp_path: Path,
) -> None:
    provided: list[WorkspaceContext] = []

    def provider(_principal_id: str) -> Sequence[WorkspaceContext]:
        return tuple(provided)

    host = _host(tmp_path, allowed_context_provider=provider)
    assert host.upsert_workspace_context(
        name="owned",
        description="owner context",
        workspace_label="owner-repo",
        principal_id="owner",
    ).ok

    provided[:] = [
        WorkspaceContext(
            id="owned",
            name="collision",
            description="collision",
            workspace_label="shared-repo",
        ),
        WorkspaceContext(
            id="duplicate",
            name="first",
            description="first",
            workspace_label="shared-repo",
        ),
        WorkspaceContext(
            id="duplicate",
            name="second",
            description="second",
            workspace_label="shared-repo",
        ),
    ]
    assert host.list_workspace_contexts("owner") == ()
    for context_id in ("owned", "duplicate"):
        with pytest.raises(KeyError):
            host.get_workspace_context(context_id, principal_id="owner")

    def failing_provider(_principal_id: str) -> Sequence[WorkspaceContext]:
        raise RuntimeError("private provider path")

    fallback = _host(tmp_path, allowed_context_provider=failing_provider)
    [owned] = fallback.list_workspace_contexts("owner")
    assert owned.id == "owned"


def test_allowed_workspace_context_open_remains_when_mutations_are_disabled(
    tmp_path: Path,
) -> None:
    def provider(_principal_id: str) -> Sequence[WorkspaceContext]:
        return (
            WorkspaceContext(
                id="shared-docs",
                name="Shared Docs",
                description="approved documentation",
                workspace_label="shared-repo",
            ),
        )

    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=False,
                runtime_activation_enabled=True,
                allowed_context_provider=provider,
            ),
        ),
        working_scope=tmp_path,
    )

    [shared] = host.list_workspace_contexts("owner")
    assert shared.actions == ("open",)
    assert shared.scope == "shared_read_only"


def test_workspace_context_write_get_and_delete(tmp_path: Path) -> None:
    host = _host(tmp_path)

    written = host.upsert_workspace_context(
        name="Docs",
        description="documentation workspace",
        workspace_label="docs-repo",
    )

    assert written.ok is True
    assert written.resource_id == "Docs"
    [context] = host.list_workspace_contexts()
    assert context.name == "Docs"
    assert context.workspace_label == "docs-repo"
    assert host.get_workspace_context("Docs").description == "documentation workspace"

    deleted = host.delete_workspace_context("Docs", confirm=True)

    assert deleted.ok is True
    assert host.list_workspace_contexts() == ()


@pytest.mark.anyio
async def test_session_context_binding_updates_session_metadata(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
            ),
        ),
        working_scope=tmp_path,
    )
    host.upsert_workspace_context(
        name="Docs",
        description="documentation workspace",
        workspace_label="docs-repo",
        principal_id="owner",
    )

    async with host.session(_discard, principal_id="owner") as session:
        bound = await host.bind_session_context(
            session.session_id,
            "Docs",
            principal_id="owner",
        )

    assert bound.context_id == "Docs"
    [summary] = host.list_sessions()
    assert summary.context_id == "Docs"
    assert summary.context_name == "Docs"
    assert summary.context_workspace_label == "docs-repo"


def test_schedule_management_is_durable_scoped_and_dispatches_safely(
    tmp_path: Path,
) -> None:
    runner = _RecordingScheduleRunner()
    host = _host(tmp_path, schedule_runner=runner)

    written = host.upsert_managed_schedule(
        name="daily-notes",
        description="refresh notes",
        trigger="manual",
        instruction="refresh documentation notes",
        enabled=True,
        principal_id="owner",
    )

    assert written.ok is True
    assert written.resource_id == "daily-notes"
    [schedule] = host.list_managed_schedules(principal_id="owner")
    assert schedule.name == "daily-notes"
    assert schedule.status == "enabled"
    assert schedule.instruction == "refresh documentation notes"
    assert host.list_managed_schedules(principal_id="other") == ()

    restarted = _host(tmp_path, schedule_runner=runner)
    durable = restarted.get_managed_schedule("daily-notes", principal_id="owner")
    assert durable.trigger == "manual"
    assert durable.instruction == "refresh documentation notes"

    run_now = restarted.run_managed_schedule_now("daily-notes", principal_id="owner")
    assert run_now.ok is True
    assert run_now.status == "running"
    [(principal_id, dispatched)] = runner.calls
    assert principal_id == "owner"
    assert dispatched.instruction == "refresh documentation notes"

    disabled = restarted.disable_managed_schedule("daily-notes", principal_id="owner")
    assert disabled.ok is True
    assert disabled.status == "disabled"
    refused = restarted.run_managed_schedule_now("daily-notes", principal_id="owner")
    assert refused.ok is False
    assert refused.status == "disabled"

    enabled = restarted.enable_managed_schedule("daily-notes", principal_id="owner")
    assert enabled.ok is True
    runner.fail = True
    failed = restarted.run_managed_schedule_now("daily-notes", principal_id="owner")
    assert failed.ok is False
    assert failed.status == "failed"
    assert failed.message == "schedule run failed"
    assert "private-runner" not in repr(
        (
            failed,
            restarted.get_managed_schedule("daily-notes", principal_id="owner"),
        )
    )

    deleted = restarted.delete_managed_schedule(
        "daily-notes", confirm=True, principal_id="owner"
    )
    assert deleted.ok is True
    assert restarted.list_managed_schedules(principal_id="owner") == ()


def test_schedule_run_now_requires_instruction_and_runner(tmp_path: Path) -> None:
    without_runner = _host(tmp_path / "without-runner")
    assert without_runner.upsert_managed_schedule(
        name="daily-notes",
        description="refresh notes",
        trigger="manual",
        instruction="refresh documentation notes",
        enabled=True,
        principal_id="owner",
    ).ok
    unavailable = without_runner.run_managed_schedule_now(
        "daily-notes", principal_id="owner"
    )
    assert unavailable.ok is False
    assert unavailable.status == "unavailable"

    runner = _RecordingScheduleRunner()
    instructionless = _host(tmp_path / "instructionless", schedule_runner=runner)
    assert instructionless.upsert_managed_schedule(
        name="legacy",
        description="legacy schedule",
        trigger="manual",
        instruction="",
        enabled=True,
        principal_id="owner",
    ).ok
    invalid = instructionless.run_managed_schedule_now("legacy", principal_id="owner")
    assert invalid.ok is False
    assert invalid.status == "invalid"
    assert runner.calls == []


def test_model_default_accepts_only_host_catalog_entries(tmp_path: Path) -> None:
    host = _host(tmp_path)

    rejected = host.set_model_default(
        "missing-model",
        available_models={"fast": "Fast model"},
        principal_id="owner",
    )

    assert rejected.ok is False
    assert rejected.status == "invalid"
    assert host.model_default(principal_id="owner").status == "fallback"

    selected = host.set_model_default(
        "fast",
        available_models={"fast": "Fast model"},
        principal_id="owner",
    )

    assert selected.ok is True
    assert host.model_default(principal_id="owner").model_id == "fast"
    assert host.model_default(principal_id="owner").label == "Fast model"
    assert host.model_default(principal_id="other").status == "fallback"

    restarted = _host(tmp_path)
    durable = restarted.model_default(
        principal_id="owner",
        available_models={"fast": "Fast model"},
    )
    assert durable.model_id == "fast"
    assert durable.status == "available"

    stale = restarted.model_default(
        principal_id="owner",
        available_models={},
    )
    assert stale.model_id == "fast"
    assert stale.status == "fallback"
    assert stale.problem == "model unavailable"

    cleared = restarted.clear_model_default(principal_id="owner")
    assert cleared.ok is True
    assert restarted.model_default(principal_id="owner").status == "fallback"
