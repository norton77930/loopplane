"""Configuration contract: fail-fast validation, from_mapping, and the
public-safe (no-secret) shape (spec US2; FR-005, FR-011, FR-013, SC-005)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy
from loopplane.host import (
    ApprovalPolicy,
    ConfigError,
    DesktopStorageAuthorityFactory,
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


def test_from_mapping_preserves_storage_authority(tmp_path: Path) -> None:
    authority = DesktopStorageAuthorityFactory(tmp_path / "profile")

    config = RuntimeConfig.from_mapping(
        {
            "model": _model(),
            "storage": {
                "root": tmp_path / "profile" / "generation-storage" / "g0",
                "checkpoint_backend": "sqlite",
                "authority": authority,
            },
        }
    )

    assert config.storage is not None
    assert config.storage.authority is authority


def test_from_mapping_preserves_the_mcp_authorization_seams() -> None:
    """084 — the two interactive-authorization collaborators must pass through like
    their siblings.

    Dropping them fails *closed* (every interactive server reports
    needs_authorization), which is safe but silent: a host that supplied a handler
    would see it discarded with no signal, and could not tell that apart from a
    server genuinely waiting for a person. Found by architecture review; the
    dataclass had the fields and this coercion did not.
    """

    class _Handler:
        def redirect_uri(self, *, server: str) -> str:
            return "http://127.0.0.1:0/callback"

        async def present(
            self, url: str, *, server: str, principal: str | None
        ) -> None:
            return None

        async def await_result(self, *, server: str, principal: str | None) -> object:
            return object()

    class _Store:
        async def load(self, *, principal: str | None, server: str) -> object | None:
            return None

        async def save(
            self, *, principal: str | None, server: str, material: object
        ) -> None:
            return None

        async def discard(self, *, principal: str | None, server: str) -> None:
            return None

    handler, store = _Handler(), _Store()
    config = RuntimeConfig.from_mapping(
        {
            "model": _model(),
            "capability_management": {
                "mutations_enabled": True,
                "mcp_authorization_handler": handler,
                "mcp_token_store": store,
            },
        }
    )

    assert config.capability_management is not None
    assert config.capability_management.mcp_authorization_handler is handler
    assert config.capability_management.mcp_token_store is store


def test_malformed_mcp_authorization_seams_are_rejected() -> None:
    """A shape error must surface as a configuration error, not as every
    interactive server quietly reporting that it needs authorizing."""
    # Shape checks run at assembly, like every other collaborator check — building
    # the config object alone does not validate it.
    with pytest.raises(ConfigError, match="mcp_authorization_handler"):
        LoopPlaneHost(
            RuntimeConfig.from_mapping(
                {
                    "model": _model(),
                    "capability_management": {"mcp_authorization_handler": object()},
                }
            )
        )
    with pytest.raises(ConfigError, match="mcp_token_store"):
        LoopPlaneHost(
            RuntimeConfig.from_mapping(
                {
                    "model": _model(),
                    "capability_management": {"mcp_token_store": object()},
                }
            )
        )


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


def test_platform_fairness_round_trips_from_mapping() -> None:
    fairness = PlatformFairness(
        PlatformFairnessPolicy(
            max_outstanding_per_tenant=2,
            max_active_model_calls=1,
            max_consecutive_starts=1,
        )
    )

    config = RuntimeConfig.from_mapping(
        {"model": _model(), "platform_fairness": fairness}
    )

    assert config.platform_fairness is fairness


def test_platform_fairness_defaults_off() -> None:
    assert RuntimeConfig(model=_model()).platform_fairness is None
    assert RuntimeConfig.from_mapping({"model": _model()}).platform_fairness is None


@pytest.mark.parametrize(
    "field",
    [
        "max_outstanding_per_tenant",
        "max_active_model_calls",
        "max_consecutive_starts",
    ],
)
def test_platform_fairness_policy_rejects_non_positive_values(field: str) -> None:
    values = {
        "max_outstanding_per_tenant": 1,
        "max_active_model_calls": 1,
        "max_consecutive_starts": 1,
    }
    values[field] = 0

    with pytest.raises(ValueError, match=field):
        PlatformFairnessPolicy(**values)


# --- plan-mode wiring (spec 038) ---------------------------------------------


def _write_file_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        name="write_file",
        description="",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        read_only=False,
    )


async def _plan_verdict(decider: object, in_plan_mode: bool) -> object:
    """Decide a non-read-only tool (write_file) against a RunContext whose plan_mode
    is active or absent — proving the installed policy denies only when the per-run
    holder is active."""
    import pathlib

    from loopplane.context import PlanModeState, RunContext
    from loopplane.model import ToolCallRequest

    request = ToolCallRequest(call_id="c", tool_name="write_file", input={})
    context = RunContext(
        session_id="s",
        working_scope=pathlib.Path("."),
        plan_mode=PlanModeState(active=True) if in_plan_mode else None,
    )
    return await decider(request, _write_file_descriptor(), context, None)  # type: ignore[operator]


def _write_tool() -> ToolSpec:
    return ToolSpec(descriptor=_write_file_descriptor(), handler=_handler)


@pytest.mark.anyio
async def test_plan_mode_decider_denies_non_read_only_when_holder_active() -> None:
    from loopplane.approval import PolicyAllow, PolicyDeny
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(model=_model(), tools=(_write_tool(),), plan_mode=True)
    decider = _build_decider(config, ["write_file"], None)
    assert decider is not None
    # Active per-run holder → write_file denied; absent holder → the installed policy
    # is a no-op (allowed), proving installing it never changes a non-plan-mode run.
    assert isinstance(await _plan_verdict(decider, True), PolicyDeny)
    assert isinstance(await _plan_verdict(decider, False), PolicyAllow)


@pytest.mark.anyio
async def test_plan_mode_off_installs_no_plan_mode_policy() -> None:
    from loopplane.approval import PolicyAllow
    from loopplane.host.assembly import _build_decider

    # With plan mode off, no plan-mode policy is installed: even a context with an
    # active plan-mode holder gets write_file ALLOWED (the existing posture — only the
    # default network gate applies, which a non-network tool passes). This proves
    # plan-mode-off is byte-identical to today for an existing run.
    config = RuntimeConfig(model=_model(), tools=(_write_tool(),))
    decider = _build_decider(config, ["write_file"], None)
    assert decider is not None  # the default network gate is present (egress off)
    assert isinstance(await _plan_verdict(decider, True), PolicyAllow)


def test_plan_mode_off_with_egress_on_keeps_the_allow_all_fast_path() -> None:
    from loopplane.host.assembly import _build_decider

    # With plan mode off, egress on, and no approval/skills, the builder keeps the
    # allow-all fast-path (None) — the existing posture is unchanged (plan mode adds
    # nothing to the gate decision).
    config = RuntimeConfig(model=_model(), tools=(_write_tool(),), allow_network=True)
    assert _build_decider(config, ["write_file"], None) is None


def test_plan_mode_round_trips_from_mapping_and_has_no_secret() -> None:
    config = RuntimeConfig.from_mapping({"model": _model(), "plan_mode": True})
    assert config.plan_mode is True
    assert RuntimeConfig.from_mapping({"model": _model()}).plan_mode is False


# --- permission-rule DSL wiring (spec 039) -----------------------------------


def _run_command_tool() -> ToolSpec:
    return ToolSpec(descriptor=_descriptor("run_command"), handler=_handler)


async def _rule_verdict(decider: object, command: str) -> object:
    """Decide a run_command call with the given `command` input against a real
    RunContext — proving the installed DSL policy denies only the matching call."""
    import pathlib

    from loopplane.context import RunContext
    from loopplane.model import ToolCallRequest

    request = ToolCallRequest(
        call_id="c", tool_name="run_command", input={"command": command}
    )
    context = RunContext(session_id="s", working_scope=pathlib.Path("."))
    return await decider(request, _descriptor("run_command"), context, None)  # type: ignore[operator]


@pytest.mark.anyio
async def test_permission_rules_decider_denies_the_matching_call() -> None:
    from loopplane.approval import PolicyAllow, PolicyDeny
    from loopplane.governance import PermissionRuleSet, PermissionRuleSpec
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(
        model=_model(),
        tools=(_run_command_tool(),),
        permission_rules=PermissionRuleSet(
            rules=(
                PermissionRuleSpec(
                    tool="run_command", match={"command": "^rm -rf"}, decision="deny"
                ),
            ),
            default="allow",
        ),
    )
    decider = _build_decider(config, ["run_command"], None)
    assert decider is not None
    assert isinstance(await _rule_verdict(decider, "rm -rf /"), PolicyDeny)
    assert isinstance(await _rule_verdict(decider, "ls -la"), PolicyAllow)


def test_no_permission_rules_keeps_the_allow_all_fast_path() -> None:
    from loopplane.host.assembly import _build_decider

    # With no permission rules (and no other gate; egress on), the builder keeps the
    # allow-all fast-path (None) — the existing posture is unchanged.
    config = RuntimeConfig(
        model=_model(), tools=(_run_command_tool(),), allow_network=True
    )
    assert _build_decider(config, ["run_command"], None) is None


def test_empty_permission_rules_keeps_the_allow_all_fast_path() -> None:
    from loopplane.governance import PermissionRuleSet
    from loopplane.host.assembly import _build_decider

    # An empty set whose default is allow installs no DSL policy (allow-all no-op).
    config = RuntimeConfig(
        model=_model(),
        tools=(_run_command_tool(),),
        allow_network=True,
        permission_rules=PermissionRuleSet(default="allow"),
    )
    assert _build_decider(config, ["run_command"], None) is None


@pytest.mark.anyio
async def test_empty_deny_permission_rules_deny_an_unmatched_call() -> None:
    from loopplane.approval import PolicyDeny
    from loopplane.governance import PermissionRuleSet
    from loopplane.host.assembly import _build_decider

    config = RuntimeConfig(
        model=_model(),
        tools=(_run_command_tool(),),
        allow_network=True,
        permission_rules=PermissionRuleSet(rules=(), default="deny"),
    )
    decider = _build_decider(config, ["run_command"], None)
    assert decider is not None
    verdict = await _rule_verdict(decider, "ls")
    assert isinstance(verdict, PolicyDeny)


@pytest.mark.anyio
async def test_empty_ask_permission_rules_ask_an_unmatched_call() -> None:
    import anyio

    from loopplane.approval import InteractionBroker, PolicyAllow
    from loopplane.context import RunContext
    from loopplane.events import EventSequencer, RuntimeEvent
    from loopplane.events.emitter import EventEmitter
    from loopplane.governance import PermissionRuleSet
    from loopplane.host.assembly import _build_decider
    from loopplane.model import ToolCallRequest

    class _Collector:
        def __init__(self) -> None:
            self.events: list[RuntimeEvent] = []

        async def __call__(self, event: RuntimeEvent) -> None:
            self.events.append(event)

    sink = _Collector()
    broker = InteractionBroker(
        emitter=EventEmitter(
            session_id="s", sequencer=EventSequencer(), sink=sink
        )
    )
    broker.attach_reviewer()
    context = RunContext(
        session_id="s", working_scope=Path("."), interactions=broker
    )
    config = RuntimeConfig(
        model=_model(),
        tools=(_run_command_tool(),),
        allow_network=True,
        permission_rules=PermissionRuleSet(rules=(), default="ask"),
    )
    decider = _build_decider(config, ["run_command"], None)
    assert decider is not None
    request = ToolCallRequest(
        call_id="c", tool_name="run_command", input={"command": "ls"}
    )
    result: list[object] = []

    async def run() -> None:
        result.append(
            await decider(request, _descriptor("run_command"), context, None)
        )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(run)
        with anyio.fail_after(5):
            while not any(
                event.type == "approval-requested" for event in sink.events
            ):
                await anyio.lowlevel.checkpoint()
        requested = next(
            event for event in sink.events if event.type == "approval-requested"
        )
        assert broker.resolve_approval(
            requested.payload.request_id, decision="allow", scope="once"
        )

    assert result and isinstance(result[0], PolicyAllow)


def test_permission_rules_round_trip_from_mapping_and_have_no_secret() -> None:
    from loopplane.governance import PermissionRuleSet

    config = RuntimeConfig.from_mapping(
        {
            "model": _model(),
            "permission_rules": {
                "rules": [
                    {
                        "tool": "run_command",
                        "match": {"command": "^rm -rf"},
                        "decision": "deny",
                    }
                ],
                "default": "allow",
            },
        }
    )
    assert isinstance(config.permission_rules, PermissionRuleSet)
    assert len(config.permission_rules.rules) == 1
    assert config.permission_rules.rules[0].tool == "run_command"
    assert config.permission_rules.default == "allow"
    assert RuntimeConfig.from_mapping({"model": _model()}).permission_rules is None
