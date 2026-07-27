"""076 principal-safe runtime activation coverage."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Literal

import anyio
import pytest

import loopplane.host.capability_manager as capability_manager_module
from loopplane.adapters.mcp import MCPServerConfig
from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.gateway.spi import AdapterOutput
from loopplane.host import (
    CapabilityManagementConfig,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.host.capability_manager import CapabilityManager
from loopplane.host.capability_store import CapabilitySettingsStore
from loopplane.loop import AgentLoop, SessionHistory
from loopplane.model import (
    ModelIncrement,
    ModelRequest,
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
    ToolResultBlock,
)

pytestmark = pytest.mark.anyio


async def _discard(_event: RuntimeEvent) -> None:
    return None


class _RecordingGateway(ToolGateway):
    def __init__(self) -> None:
        super().__init__()
        self.descriptor_principals: list[str | None] = []
        self.concurrency_principals: list[str | None] = []

    def descriptors(self, principal_id: str | None = None) -> list[ToolDescriptor]:
        self.descriptor_principals.append(principal_id)
        return super().descriptors(principal_id)

    def is_concurrency_safe(
        self, tool_name: str, principal_id: str | None = None
    ) -> bool:
        self.concurrency_principals.append(principal_id)
        return super().is_concurrency_safe(tool_name, principal_id)


class _RecordingModel(ScriptedModel):
    def __init__(self, script: list[ScriptEntry]) -> None:
        super().__init__(script=script, context_capacity=1000)
        self.requests: list[ModelRequest] = []

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.requests.append(request)
        async for increment in super().stream_turn(request):
            yield increment


class _ManagedAdapter:
    def __init__(self) -> None:
        self.invocations: list[str | None] = []

    def describe(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name="managed",
                description="owner-managed tool",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                concurrency_safe=True,
            )
        ]

    async def invoke(
        self,
        name: str,
        call_input: dict[str, object],
        context: RunContext,
    ) -> AsyncIterator[AdapterOutput]:
        self.invocations.append(context.principal_id)
        yield TextBlock(text="managed result")

    async def shutdown(self) -> None:
        return None


class _RuntimeMcpAdapter:
    invocations: list[str | None] = []

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
                description="managed MCP lookup",
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
        self.invocations.append(context.principal_id)
        yield TextBlock(text="managed MCP result")

    async def shutdown(self) -> None:
        return None


_LifecycleMode = Literal[
    "ok",
    "connect_error",
    "connection_failure",
    "describe_error",
]


class _LifecycleMcpAdapter:
    instances: list[_LifecycleMcpAdapter] = []
    next_mode: _LifecycleMode = "ok"

    def __init__(self, configs: Sequence[MCPServerConfig]) -> None:
        [self.config] = configs
        self.mode = type(self).next_mode
        type(self).next_mode = "ok"
        self.block_invocation = False
        self.started = anyio.Event()
        self.release = anyio.Event()
        self.shutdown_calls = 0
        type(self).instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.next_mode = "ok"

    @property
    def connection_failures(self) -> dict[str, str]:
        if self.mode == "connection_failure":
            return {self.config.name: "private connection detail"}
        return {}

    async def connect(self) -> None:
        if self.mode == "connect_error":
            raise RuntimeError("private connect failure")

    def describe(self) -> list[ToolDescriptor]:
        if self.mode == "describe_error":
            raise RuntimeError("private descriptor failure")
        return [
            ToolDescriptor(
                name=f"{self.config.name}:lookup",
                description="managed MCP lookup",
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
        self.started.set()
        if self.block_invocation:
            await self.release.wait()
        yield TextBlock(text=f"managed MCP result for {context.principal_id}")

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


def _script() -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                ToolCallRequest(call_id="call-1", tool_name="managed", input={})
            ]
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


def _skill_script() -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="skill-call",
                    tool_name="skill:writer",
                    input={"arguments": "draft"},
                )
            ]
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


def _mcp_script() -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="mcp-call",
                    tool_name="docs:lookup",
                    input={},
                )
            ]
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


def _request_text(request: ModelRequest) -> str:
    return "\n".join(
        block.text
        for message in request.context
        for block in message.blocks
        if isinstance(block, TextBlock)
    )


def _tool_result_text(request: ModelRequest) -> str:
    return "\n".join(
        output.text
        for message in request.context
        for block in message.blocks
        if isinstance(block, ToolResultBlock)
        for output in block.outputs
        if isinstance(output, TextBlock)
    )


async def _run(
    tmp_path: Path,
    *,
    gateway: ToolGateway,
    model: ScriptedModel,
    principal_id: str,
) -> None:
    loop = AgentLoop(
        model=model,
        gateway=gateway,
        emitter=EventEmitter(
            session_id=f"session-{principal_id}",
            sequencer=EventSequencer(),
            sink=_discard,
        ),
        history=SessionHistory(),
    )
    await loop.run(
        [TextBlock(text="go")],
        RunContext(
            session_id=f"session-{principal_id}",
            working_scope=tmp_path,
            principal_id=principal_id,
        ),
    )


async def _execute_managed_call(
    gateway: ToolGateway,
    tmp_path: Path,
    principal_id: str,
    results: list[ToolResultBlock],
) -> None:
    results.extend(
        await gateway.execute_batch(
            [
                ToolCallRequest(
                    call_id=f"call-{principal_id}",
                    tool_name="docs:lookup",
                    input={},
                )
            ],
            parallel=False,
            context=RunContext(
                session_id=f"session-{principal_id}",
                working_scope=tmp_path,
                principal_id=principal_id,
            ),
            emitter=EventEmitter(
                session_id=f"session-{principal_id}",
                sequencer=EventSequencer(),
                sink=_discard,
            ),
        )
    )


async def _lifecycle_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    CapabilityManager,
    CapabilitySettingsStore,
    ToolGateway,
    dict[str, bool],
    _LifecycleMcpAdapter,
    _LifecycleMcpAdapter,
]:
    _LifecycleMcpAdapter.reset()
    monkeypatch.setattr(
        capability_manager_module,
        "MCPToolAdapter",
        _LifecycleMcpAdapter,
        raising=False,
    )
    policy = {"allowed": True}
    gateway = ToolGateway()
    store = CapabilitySettingsStore(tmp_path / "store")
    manager = CapabilityManager(
        config=CapabilityManagementConfig(
            mutations_enabled=True,
            runtime_activation_enabled=True,
            mcp_endpoint_policy=lambda *_args: policy["allowed"],
        ),
        store=store,
        gateway=gateway,
    )
    for principal_id in ("alice", "bob"):
        saved = await manager.upsert_mcp(
            name="docs",
            transport="http",
            url=f"https://{principal_id}.example.invalid",
            command=None,
            args=(),
            principal_id=principal_id,
        )
        assert saved.ok
        connected = await manager.reconnect_mcp("docs", principal_id=principal_id)
        assert connected.ok
    alice, bob = _LifecycleMcpAdapter.instances
    alice.block_invocation = True
    return manager, store, gateway, policy, alice, bob


async def test_agent_loop_threads_principal_to_scoped_tools(
    tmp_path: Path,
) -> None:
    gateway = _RecordingGateway()
    adapter = _ManagedAdapter()
    await gateway.replace_scoped_adapter("alice", "docs", adapter)

    owner_model = _RecordingModel(_script())
    await _run(
        tmp_path,
        gateway=gateway,
        model=owner_model,
        principal_id="alice",
    )

    assert {tool.name for tool in owner_model.requests[0].tools} == {"managed"}
    assert gateway.descriptor_principals[:2] == ["alice", "alice"]
    assert gateway.concurrency_principals[0] == "alice"
    assert adapter.invocations == ["alice"]

    other_model = _RecordingModel(_script())
    await _run(
        tmp_path,
        gateway=gateway,
        model=other_model,
        principal_id="bob",
    )

    assert other_model.requests[0].tools == []
    assert gateway.descriptor_principals[2:] == ["bob", "bob"]
    assert gateway.concurrency_principals[-1] == "bob"
    assert adapter.invocations == ["alice"]


async def test_owned_memory_activates_after_restart_for_owner_only(
    tmp_path: Path,
) -> None:
    storage = StorageConfig(root=tmp_path / "store")
    writer = LoopPlaneHost(
        RuntimeConfig(
            model=_RecordingModel([]),
            storage=storage,
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=True,
            ),
        ),
        working_scope=tmp_path,
    )
    assert writer.write_managed_memory(
        name="deploy-note",
        kind="project",
        description="deployment guidance",
        content="owner-only smoke sequence",
        principal_id="alice",
    ).ok
    await writer.aclose()

    model = _RecordingModel(
        [
            ScriptedTurn(increments=[TextIncrement(text="owner done")]),
            ScriptedTurn(increments=[TextIncrement(text="other done")]),
            ScriptedTurn(increments=[TextIncrement(text="disabled done")]),
        ]
    )
    activated = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=storage,
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=True,
            ),
        ),
        working_scope=tmp_path,
    )

    await activated.run("deploy", _discard, principal_id="alice")
    await activated.run("deploy", _discard, principal_id="bob")
    await activated.aclose()

    disabled = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=storage,
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=False,
            ),
        ),
        working_scope=tmp_path,
    )
    await disabled.run("deploy", _discard, principal_id="alice")
    await disabled.aclose()

    assert "owner-only smoke sequence" in _request_text(model.requests[0])
    assert "owner-only smoke sequence" not in _request_text(model.requests[1])
    assert "owner-only smoke sequence" not in _request_text(model.requests[2])


async def test_owned_skill_descriptor_and_execution_are_owner_scoped(
    tmp_path: Path,
) -> None:
    model = _RecordingModel(_skill_script() + _skill_script())
    host = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=True,
            ),
        ),
        working_scope=tmp_path,
    )
    assert host.write_managed_skill(
        name="writer",
        description="owner writer",
        instructions="owner skill instructions for ${arguments}",
        principal_id="alice",
    ).ok

    await host.run("write", _discard, principal_id="alice")
    await host.run("write", _discard, principal_id="bob")
    await host.aclose()

    assert {tool.name for tool in model.requests[0].tools} == {"skill:writer"}
    assert "owner skill instructions for draft" in _tool_result_text(model.requests[1])
    assert model.requests[2].tools == []
    assert "owner skill instructions" not in _tool_result_text(model.requests[3])


async def test_reconnected_mcp_tools_activate_for_owner_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _RuntimeMcpAdapter.invocations = []
    monkeypatch.setattr(
        capability_manager_module,
        "MCPToolAdapter",
        _RuntimeMcpAdapter,
        raising=False,
    )
    model = _RecordingModel(_mcp_script() + _mcp_script())
    host = LoopPlaneHost(
        RuntimeConfig(
            model=model,
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                runtime_activation_enabled=True,
                mcp_endpoint_policy=lambda *_args: True,
            ),
        ),
        working_scope=tmp_path,
    )
    assert (
        await host.upsert_managed_mcp(
            name="docs",
            transport="http",
            url="https://mcp.example.invalid",
            principal_id="alice",
        )
    ).ok
    assert (await host.reconnect_managed_mcp("docs", principal_id="alice")).ok

    await host.run("lookup", _discard, principal_id="alice")
    await host.run("lookup", _discard, principal_id="bob")
    await host.aclose()

    assert {tool.name for tool in model.requests[0].tools} == {"docs:lookup"}
    assert "managed MCP result" in _tool_result_text(model.requests[1])
    assert model.requests[2].tools == []
    assert "managed MCP result" not in _tool_result_text(model.requests[3])
    assert _RuntimeMcpAdapter.invocations == ["alice"]


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expect_record", "expect_visible"),
    [
        ("update", "disconnected", True, False),
        ("delete", None, False, False),
        ("structural_invalidity", "invalid", True, False),
        ("policy_denial", "invalid", True, False),
        ("connect_error", "failed", True, False),
        ("connection_failure", "failed", True, False),
        ("describe_error", "failed", True, False),
        ("state_write_failure", "connected", True, False),
        ("registry_replacement_failure", "failed", True, False),
        ("successful_reconnect", "connected", True, True),
    ],
)
async def test_managed_mcp_terminal_paths_retire_with_lease_and_principal_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_status: str | None,
    expect_record: bool,
    expect_visible: bool,
) -> None:
    manager, store, gateway, policy, alice, bob = await _lifecycle_manager(
        tmp_path, monkeypatch
    )
    results: list[ToolResultBlock] = []

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(
            _execute_managed_call,
            gateway,
            tmp_path,
            "alice",
            results,
        )
        await alice.started.wait()

        if scenario == "update":
            outcome = await manager.upsert_mcp(
                name="docs",
                transport="http",
                url="https://updated.example.invalid",
                command=None,
                args=(),
                principal_id="alice",
            )
        elif scenario == "delete":
            outcome = await manager.delete_mcp(
                "docs", principal_id="alice", confirm=True
            )
        elif scenario == "structural_invalidity":
            outcome = await manager.upsert_mcp(
                name="docs",
                transport="http",
                url="https://alice.example.invalid?private=credential",
                command=None,
                args=(),
                principal_id="alice",
            )
        elif scenario == "policy_denial":
            policy["allowed"] = False
            outcome = await manager.reconnect_mcp("docs", principal_id="alice")
        elif scenario in {
            "connect_error",
            "connection_failure",
            "describe_error",
        }:
            _LifecycleMcpAdapter.next_mode = scenario
            outcome = await manager.reconnect_mcp("docs", principal_id="alice")
        elif scenario == "state_write_failure":

            def reject_state_write(*_args: object, **_kwargs: object) -> bool:
                return False

            monkeypatch.setattr(manager, "_update_mcp_record", reject_state_write)
            outcome = await manager.reconnect_mcp("docs", principal_id="alice")
        elif scenario == "registry_replacement_failure":

            async def reject_replacement(*_args: object, **_kwargs: object) -> None:
                raise RuntimeError("private registry failure")

            monkeypatch.setattr(gateway, "replace_scoped_adapter", reject_replacement)
            outcome = await manager.reconnect_mcp("docs", principal_id="alice")
        else:
            outcome = await manager.reconnect_mcp("docs", principal_id="alice")

        alice_tools = {descriptor.name for descriptor in gateway.descriptors("alice")}
        bob_tools = {descriptor.name for descriptor in gateway.descriptors("bob")}
        assert ("docs:lookup" in alice_tools) is expect_visible
        assert "docs:lookup" in bob_tools
        assert alice.shutdown_calls == 0
        assert bob.shutdown_calls == 0
        assert "credential" not in outcome.message
        assert "private" not in outcome.message
        alice.release.set()

    assert len(results) == 1
    assert results[0].outcome == "success"
    assert "managed MCP result for alice" in str(results[0].outputs)
    assert alice.shutdown_calls == 1
    assert bob.shutdown_calls == 0

    state = store.load("alice")
    assert ("docs" in state.mcp) is expect_record
    if expect_record:
        assert state.mcp["docs"]["status"] == expected_status

    candidates = _LifecycleMcpAdapter.instances[2:]
    if scenario in {
        "connect_error",
        "connection_failure",
        "describe_error",
        "state_write_failure",
        "registry_replacement_failure",
    }:
        assert len(candidates) == 1
        assert candidates[0].shutdown_calls == 1
    elif scenario == "successful_reconnect":
        assert len(candidates) == 1
        assert candidates[0].shutdown_calls == 0
    else:
        assert candidates == []

    await gateway.remove_scoped_adapter("alice", "managed-mcp:docs")
    await gateway.remove_scoped_adapter("bob", "managed-mcp:docs")
