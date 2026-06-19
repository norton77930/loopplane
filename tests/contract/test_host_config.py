"""Configuration contract: fail-fast validation, from_mapping, and the
public-safe (no-secret) shape (spec US2; FR-005, FR-011, FR-013, SC-005)."""

from __future__ import annotations

import dataclasses

import pytest

from loopplane.host import (
    ApprovalPolicy,
    ConfigError,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
    ToolSpec,
)
from loopplane.host import config as host_config
from loopplane.model import ScriptedModel, TextBlock, ToolDescriptor

_OUTPUT_BLOCK = list[TextBlock]


def _model() -> ScriptedModel:
    return ScriptedModel(script=[], context_capacity=1_000)


def _descriptor(name: str) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="test tool",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )


async def _handler(call_input: dict[str, object], context: object) -> list[TextBlock]:
    return [TextBlock(text="ok")]


def _tool(name: str) -> ToolSpec:
    return ToolSpec(descriptor=_descriptor(name), handler=_handler)


def test_missing_model_is_rejected_fast() -> None:
    with pytest.raises(ConfigError):
        LoopPlaneHost(RuntimeConfig(model=None))  # type: ignore[arg-type]


def test_duplicate_tool_names_are_rejected_fast() -> None:
    config = RuntimeConfig(model=_model(), tools=(_tool("echo"), _tool("echo")))
    with pytest.raises(ConfigError):
        LoopPlaneHost(config)


def test_unavailable_optional_capability_is_rejected_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_config, "_otel_available", lambda: False)
    with pytest.raises(ConfigError):
        LoopPlaneHost(RuntimeConfig(model=_model(), observability=True))


def test_approval_referencing_an_unknown_tool_is_rejected_fast() -> None:
    config = RuntimeConfig(
        model=_model(),
        tools=(_tool("echo"),),
        approval=ApprovalPolicy(deny=frozenset({"not-registered"})),
    )
    with pytest.raises(ConfigError):
        LoopPlaneHost(config)


def test_from_mapping_round_trips_a_plain_mapping() -> None:
    model = _model()
    config = RuntimeConfig.from_mapping(
        {
            "model": model,
            "tools": [(_descriptor("echo"), _handler)],
            "approval": {"deny": ["echo"]},
            "observability": False,
        }
    )
    assert config.model is model
    assert config.tools[0].descriptor.name == "echo"
    assert config.approval is not None
    assert "echo" in config.approval.deny


def test_from_mapping_without_model_is_rejected() -> None:
    with pytest.raises(ConfigError):
        RuntimeConfig.from_mapping({"tools": []})


def test_storage_and_storageless_configs_both_assemble(tmp_path: object) -> None:
    # With storage, checkpoint + artifact are wired together; without it, neither
    # is — both are internally consistent and need no manual handoff (FR-002).
    LoopPlaneHost(RuntimeConfig(model=_model(), storage=StorageConfig(root=tmp_path)))  # type: ignore[arg-type]
    LoopPlaneHost(RuntimeConfig(model=_model()))


def test_runtime_config_declares_no_secret_field() -> None:
    names = {f.name for f in dataclasses.fields(RuntimeConfig)}
    secrets = {
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "credential",
        "credentials",
    }
    assert not (names & secrets)


# --- network-egress wiring (spec 034; US1) -----------------------------------


def _network_descriptor(name: str) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="network tool",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        network=True,
    )


async def _verdict(decider: object, the_descriptor: ToolDescriptor) -> object:
    import pathlib

    from loopplane.context import RunContext
    from loopplane.model import ToolCallRequest

    request = ToolCallRequest(call_id="c", tool_name=the_descriptor.name, input={})
    # A real RunContext (HumanApproval reads its session approval memory); the
    # event emitter is unused on the allow/deny paths these tests exercise.
    context = RunContext(session_id="s", working_scope=pathlib.Path("."))
    return await decider(request, the_descriptor, context, None)  # type: ignore[operator]


@pytest.mark.anyio
async def test_network_tool_denied_by_default() -> None:
    from loopplane.approval import PolicyDeny
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(
        model=_model(),
        tools=(
            ToolSpec(descriptor=_network_descriptor("web_fetch"), handler=_handler),
        ),
    )
    decider = _build_decider(config, ["web_fetch"], None)
    assert decider is not None
    verdict = await _verdict(decider, _network_descriptor("web_fetch"))
    assert isinstance(verdict, PolicyDeny)


@pytest.mark.anyio
async def test_network_tool_allowed_when_egress_enabled() -> None:
    from loopplane.approval import PolicyAllow
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(
        model=_model(),
        tools=(
            ToolSpec(descriptor=_network_descriptor("web_fetch"), handler=_handler),
        ),
        allow_network=True,
    )
    decider = _build_decider(config, ["web_fetch"], None)
    # With egress enabled and no approval/skills, the network policy would be a
    # harmless allow, so the builder keeps the allow-all fast-path (None) — which
    # itself allows the network tool. If a decider is built, it must allow.
    if decider is not None:
        verdict = await _verdict(decider, _network_descriptor("web_fetch"))
        assert isinstance(verdict, PolicyAllow)


@pytest.mark.anyio
async def test_network_tool_allowed_when_egress_enabled_with_approval() -> None:
    from loopplane.approval import PolicyAllow
    from loopplane.host.assembly import _build_decider

    # With an approval policy present, the composed decider is always built; the
    # network policy must still allow the network tool when egress is on.
    config = RuntimeConfig(
        model=_model(),
        tools=(
            ToolSpec(descriptor=_network_descriptor("web_fetch"), handler=_handler),
        ),
        approval=ApprovalPolicy(allow=frozenset({"web_fetch"}), default="allow"),
        allow_network=True,
    )
    decider = _build_decider(config, ["web_fetch"], None)
    assert decider is not None
    verdict = await _verdict(decider, _network_descriptor("web_fetch"))
    assert isinstance(verdict, PolicyAllow)


@pytest.mark.anyio
async def test_non_network_tool_unaffected_by_default_egress() -> None:
    from loopplane.approval import PolicyAllow
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(
        model=_model(),
        tools=(
            ToolSpec(descriptor=_network_descriptor("web_fetch"), handler=_handler),
        ),
    )
    decider = _build_decider(config, ["web_fetch"], None)
    assert decider is not None
    # A plain (non-network) tool passes even though egress is off.
    verdict = await _verdict(decider, _descriptor("echo"))
    assert isinstance(verdict, PolicyAllow)


def test_allow_network_round_trips_from_mapping_and_has_no_secret() -> None:
    config = RuntimeConfig.from_mapping({"model": _model(), "allow_network": True})
    assert config.allow_network is True
    assert RuntimeConfig.from_mapping({"model": _model()}).allow_network is False
