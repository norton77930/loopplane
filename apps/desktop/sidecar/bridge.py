"""Desktop stdio sidecar entry (feature 019 + 078 T024/T025/T026).

Legacy ``{op: run}`` helpers remain for integration tests. The launchable
``main`` path negotiates JSON-RPC V1 before expensive runtime composition, then
acquires the Profile Ownership Lock and bootstraps generation via
``validate_active_generation`` before constructing Host-backed methods.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from profile import ProfileState

    from runtime import DesktopRuntimeOwner

    from loopplane.events import RuntimeEvent
    from loopplane.host import LoopPlaneHost, RuntimeConfig

ReadLine = Callable[[], Awaitable[str | None]]
WriteLine = Callable[[str], None]
WriteFrame = Callable[[dict[str, Any]], None]


async def collect_events(host: LoopPlaneHost, prompt: str) -> list[str]:
    """Drive one run; return the serialized event lines plus an outcome line.

    The testable core: each normalized event becomes one ``serialize_event`` line,
    and the run's terminal outcome is the final line.
    """
    from loopplane.events import serialize_event

    lines: list[str] = []

    async def sink(event: RuntimeEvent) -> None:
        lines.append(serialize_event(event))

    outcome = await host.run(prompt, sink)
    lines.append(
        json.dumps(
            {
                "op": "outcome",
                "reason": outcome.termination_reason,
                "turns": outcome.turns_taken,
            }
        )
    )
    return lines


async def serve(
    host: LoopPlaneHost, read_line: ReadLine, write_line: WriteLine
) -> None:
    """Legacy NDJSON ``{op: run}`` loop (tests/smoke). Prefer ``serve_rpc``."""

    while True:
        line = await read_line()
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (ValueError, TypeError):
            write_line(json.dumps({"op": "error", "detail": "malformed request"}))
            continue
        if request.get("op") == "run":
            await _run(host, str(request.get("prompt", "")), write_line)


async def _run(host: LoopPlaneHost, prompt: str, write_line: WriteLine) -> None:
    from loopplane.events import serialize_event

    async def sink(event: RuntimeEvent) -> None:
        write_line(serialize_event(event))

    try:
        outcome = await host.run(prompt, sink)
    except RuntimeError:
        write_line(json.dumps({"op": "error", "detail": "a run is already active"}))
        return
    write_line(
        json.dumps(
            {
                "op": "outcome",
                "reason": outcome.termination_reason,
                "turns": outcome.turns_taken,
            }
        )
    )


async def serve_rpc(
    dispatcher: object,
    read_line: ReadLine,
    write_line: WriteLine | None = None,
    *,
    write_frame: WriteFrame | None = None,
) -> None:
    """JSON-RPC V1 loop over an injected dispatcher (no Host construction here)."""

    if (write_line is None) == (write_frame is None):
        raise ValueError("exactly one RPC writer is required")

    def emit(frame: dict[str, Any]) -> None:
        if write_frame is not None:
            write_frame(frame)
            return
        assert write_line is not None
        write_line(json.dumps(frame, separators=(",", ":")))

    handle_frame = dispatcher.handle_frame  # type: ignore[attr-defined]
    try:
        while True:
            line = await read_line()
            if line is None:
                break
            raw = line if isinstance(line, (bytes, bytearray)) else line
            if isinstance(raw, str) and not raw.strip():
                continue
            responses = await handle_frame(raw)
            for msg in responses:
                emit(msg)
    finally:
        teardown = getattr(dispatcher, "aclose", None)
        if callable(teardown):
            result = teardown()
            if result is not None:
                await result


def bootstrap_desktop_owner(profile_root: Path) -> DesktopRuntimeOwner:
    """Acquire and adjudicate restore authority before any Host composition."""

    from runtime import DesktopRuntimeOwner

    owner = DesktopRuntimeOwner(profile_root=profile_root)
    owner.acquire()
    try:
        owner.bootstrap_generation()
    except Exception:
        owner.release()
        raise
    return owner


def desktop_runtime_config(
    *, model: Any, profile_root: Path, generation_id: str
) -> RuntimeConfig:
    """Compose Desktop's required SQLite storage below one active generation id."""

    from loopplane.host import (
        DesktopStorageAuthorityFactory,
        RuntimeConfig,
        StorageConfig,
    )

    try:
        from .durability import initialize_runtime_storage
    except ImportError:  # pragma: no cover
        from durability import initialize_runtime_storage

    storage_root = initialize_runtime_storage(profile_root, generation_id)
    return RuntimeConfig(
        model=model,
        storage=StorageConfig(
            authority=DesktopStorageAuthorityFactory(profile_root),
            checkpoint_backend="sqlite",
            root=storage_root,
        ),
    )


def build_rpc_dispatcher(
    host: LoopPlaneHost,
    *,
    working_scope: Path | None = None,
    write_line: WriteLine | None = None,
    write_frame: WriteFrame | None = None,
    on_shutdown: Callable[[], Awaitable[None] | None] | None = None,
    profile_state: ProfileState | None = None,
    mutation_lease: object | None = None,
    principal_id: str | None = None,
    runtime_config: RuntimeConfig | None = None,
    runtime_owner: DesktopRuntimeOwner | None = None,
    configured_model_id: str | None = None,
) -> object:
    """Compose dispatcher + Host-only methods after bootstrap."""

    from dispatcher import Dispatcher
    from interaction import InteractionLease
    from methods.audit import AuditMethods
    from methods.backup import BackupMethods
    from methods.capability import CapabilityMethods
    from methods.command import CommandMethods
    from methods.cost import CostMethods
    from methods.governance import GovernanceMethods
    from methods.inspection import InspectionMethods
    from methods.interaction import InteractionMethods
    from methods.projects import ProjectMethods
    from methods.sessions import SessionMethods
    from methods.workspace import WorkspaceMethods
    from mutation_lease import ProfileMutationLease
    from restore import RestoreManager
    from runtime import RuntimeHostHandover

    lease = InteractionLease()
    mut_lease = (
        mutation_lease
        if isinstance(mutation_lease, ProfileMutationLease)
        else ProfileMutationLease()
    )
    notifications: list[dict] = []
    shutting_down = {"value": False}
    dispatcher: Dispatcher | None = None

    async def emit_notification(method: str, payload: dict) -> None:
        if shutting_down["value"]:
            return
        if dispatcher is None:
            raise RuntimeError("dispatcher notification before composition")
        frame = dispatcher.next_notification(method, payload)
        if write_frame is not None:
            write_frame(frame)
            return
        if write_line is not None:
            write_line(json.dumps(frame, separators=(",", ":")))
            return
        notifications.append(frame)

    async def emit_event(payload: dict) -> None:
        await emit_notification("runtime.event", payload)

    async def emit_outcome(payload: dict) -> None:
        await emit_notification("runtime.outcome", payload)

    async def emit_state(payload: dict) -> None:
        await emit_notification("runtime.state", payload)

    async def emit_closed(payload: dict) -> None:
        await emit_notification("runtime.subscriptionClosed", payload)

    workspace_store = None
    project_store = None
    host_for_methods: object = host
    handover: RuntimeHostHandover | None = None
    if profile_state is not None:
        if runtime_owner is not None and runtime_owner.host is not host:
            raise RuntimeError("runtime owner Host does not match dispatcher Host")
        from projects import ProjectStore
        from workspace import WorkspaceStore

        workspace_store = WorkspaceStore(profile_state)  # type: ignore[arg-type]
        project_store = ProjectStore(profile_state)  # type: ignore[arg-type]
        handover = RuntimeHostHandover(
            host,
            profile_root=profile_state.root,  # type: ignore[attr-defined]
            config=runtime_config,
            host_changed=(
                runtime_owner.adopt_handover_host if runtime_owner is not None else None
            ),
        )
        host_for_methods = handover

    follow_profile_principal = profile_state is not None and (
        principal_id is None or principal_id == profile_state.principal_id
    )

    def current_principal() -> str | None:
        if follow_profile_principal and profile_state is not None:
            return profile_state.principal_id
        return principal_id

    methods = InteractionMethods(
        host_for_methods,  # type: ignore[arg-type]
        lease,
        working_scope=working_scope,
        emit_event=emit_event,
        emit_outcome=emit_outcome,
        emit_state=emit_state,
        emit_closed=emit_closed,
        workspace_store=workspace_store,
        mutation_lease=mut_lease,
        principal_id=principal_id,
        principal_provider=current_principal,
    )
    handlers = methods.handlers()
    backup_methods: BackupMethods | None = None
    handlers.update(
        SessionMethods(
            host_for_methods,  # type: ignore[arg-type]
            mut_lease,
            principal_id=principal_id,
            principal_provider=current_principal,
            project_store=project_store,
        ).handlers()
    )
    handlers.update(
        InspectionMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
            mutation_lease=mut_lease,
            configured_model_id=configured_model_id,
        ).handlers()
    )
    handlers.update(
        CostMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
        ).handlers()
    )
    handlers.update(
        CapabilityMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
            mutation_lease=mut_lease,
        ).handlers()
    )
    handlers.update(
        GovernanceMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
            mutation_lease=mut_lease,
            configured_model_id=configured_model_id,
        ).handlers()
    )
    handlers.update(
        CommandMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
            mutation_lease=mut_lease,
            configured_model_id=configured_model_id,
        ).handlers()
    )
    handlers.update(
        AuditMethods(
            host_for_methods,  # type: ignore[arg-type]
            principal_id=principal_id,
            principal_provider=current_principal,
        ).handlers()
    )
    if profile_state is not None:
        # Backup/restore uses the existing Desktop-only Host snapshot facade.
        # This direct dispatcher composition is also used by integration tests.
        host.enable_desktop_portable_snapshot()
        handlers.update(ProjectMethods(profile_state, mut_lease).handlers())  # type: ignore[arg-type]
        handlers.update(WorkspaceMethods(profile_state, mut_lease).handlers())  # type: ignore[arg-type]
        backup_methods = BackupMethods(
            host_for_methods,  # type: ignore[arg-type]
            profile_state,  # type: ignore[arg-type]
            mut_lease,
            interaction_lease=lease,
            restore_manager=RestoreManager(profile_state.root),  # type: ignore[attr-defined]
            candidate_ready=handover.candidate_ready if handover is not None else None,
            close_previous=handover.close_previous if handover is not None else None,
            install_candidate=handover.install_candidate
            if handover is not None
            else None,
            commit_candidate=handover.commit_candidate
            if handover is not None
            else None,
            rollback_candidate=handover.rollback_candidate
            if handover is not None
            else None,
            lock_dispatch=handover.lock_dispatch if handover is not None else None,
            unlock_dispatch_after_rollback=(
                handover.unlock_dispatch_after_rollback
                if handover is not None
                else None
            ),
        )
        handlers.update(backup_methods.handlers())

    torn_down = {"value": False}

    async def teardown() -> None:
        if torn_down["value"]:
            return
        await lease.shutdown()
        shutting_down["value"] = True
        if backup_methods is not None:
            backup_methods.shutdown()
        if handover is not None:
            await handover.aclose()
        elif on_shutdown is not None:
            result = on_shutdown()
            if result is not None:
                await result
        torn_down["value"] = True

    async def system_shutdown(_params: dict) -> dict:
        # Bounded teardown only: it starts no durable work.
        await teardown()
        return {"ok": True}

    handlers["system.shutdown"] = system_shutdown

    dispatcher = Dispatcher(
        methods=handlers,
        capabilities={
            "sessions": "available",
            "interaction": "available",
            "inspection": "available",
            "backup": "available" if profile_state is not None else "unavailable",
            "projects": "available" if profile_state is not None else "unavailable",
            "workspace": "available" if profile_state is not None else "unavailable",
        },
    )
    dispatcher.aclose = teardown
    return dispatcher


_DESKTOP_METHOD_NAMES = (
    "agentControls.get",
    "audit.list",
    "backup.create",
    "backup.describe",
    "capabilities.invokeAction",
    "capabilities.list",
    "command.execute",
    "context.bind",
    "context.delete",
    "context.get",
    "context.list",
    "context.upsert",
    "cost.get",
    "inspection.get",
    "interaction.answerApproval",
    "interaction.answerQuestion",
    "interaction.cancel",
    "interaction.submit",
    "mcp.delete",
    "mcp.get",
    "mcp.list",
    "mcp.reconnect",
    "mcp.upsert",
    "memory.delete",
    "memory.get",
    "memory.list",
    "memory.write",
    "modelDefault.clear",
    "modelDefault.get",
    "modelDefault.set",
    "project.assignSession",
    "project.create",
    "project.list",
    "project.remove",
    "project.rename",
    "restore.cancel",
    "restore.commit",
    "restore.validate",
    "schedule.delete",
    "schedule.disable",
    "schedule.enable",
    "schedule.get",
    "schedule.list",
    "schedule.runNow",
    "schedule.upsert",
    "session.createInteractive",
    "session.delete",
    "session.fork",
    "session.history",
    "session.list",
    "session.releaseInteractive",
    "session.rename",
    "session.resumeInteractive",
    "session.setStarred",
    "skill.delete",
    "skill.get",
    "skill.import",
    "skill.list",
    "skill.write",
    "workspace.bind",
    "workspace.list",
    "workspace.relink",
    "workspace.remove",
    "workspace.revalidate",
)
_DESKTOP_CAPABILITIES = {
    "sessions": "available",
    "interaction": "available",
    "inspection": "available",
    "backup": "available",
    "projects": "available",
    "workspace": "available",
}


async def _runtime_not_ready(_params: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("runtime not ready")


def build_initialize_dispatcher() -> object:
    """Validate and answer initialize before expensive Host composition."""

    from dispatcher import Dispatcher

    return Dispatcher(
        methods={name: _runtime_not_ready for name in _DESKTOP_METHOD_NAMES},
        capabilities=dict(_DESKTOP_CAPABILITIES),
    )


_SMOKE_RESPONSES = {
    "happy": "loopplane-packaged-smoke-ok",
    "missing-sidecar": "runtime missing",
    "corrupt-sidecar": "runtime corrupt",
    "incompatible-sidecar": "runtime incompatible",
}


DESKTOP_PROVIDER_ENV = "LOOPPLANE_DESKTOP_PROVIDER"
DESKTOP_MODEL_ID_ENV = "LOOPPLANE_DESKTOP_MODEL_ID"
DESKTOP_API_KEY_ENV = "LOOPPLANE_DESKTOP_API_KEY"

_UNCONFIGURED_DEMO_TEXT = "LoopPlane demo model: no provider is configured."
_UNUSABLE_DEMO_TEXT = (
    "LoopPlane demo model: the configured provider could not be started. "
    "Check the provider, model id, and key in Settings."
)


# Each builder imports its adapter statically, inside the function. The import
# statement is what `tests/contract/test_desktop_boundary.py` scans (it walks the
# whole AST, not only module scope), so the edge is visible to the audit — see
# ADR 0016 D5, which widened `RUNTIME_ALLOWED_PREFIXES` to admit
# `loopplane.adapters` for model construction. Keeping the imports inside the
# functions also keeps them off the module-load path: `main()` answers
# `initialize` from a lightweight dispatcher before composing anything
# expensive, and a cold packaged start has a fixed handshake deadline.


def _build_anthropic(model_id: str, api_key: str | None) -> Any:
    from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel

    return AnthropicModel(AnthropicConfig(model=model_id, api_key=api_key))


def _build_openai(model_id: str, api_key: str | None) -> Any:
    from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

    return OpenAIModel(OpenAIConfig(model=model_id, api_key=api_key))


def _build_gemini(model_id: str, api_key: str | None) -> Any:
    from loopplane.adapters.gemini import GeminiConfig, GeminiModel

    return GeminiModel(GeminiConfig(model=model_id, api_key=api_key))


def _build_openrouter(model_id: str, api_key: str | None) -> Any:
    from loopplane.adapters.openai_compat import openrouter_model

    return openrouter_model(model_id, api_key=api_key)


def _build_ollama(model_id: str, _api_key: str | None) -> Any:
    from loopplane.adapters.openai_compat import ollama_model

    return ollama_model(model_id)


class DesktopProvider:
    """One provider the in-app setting can select.

    A plain class, not a dataclass: ``tests/integration/test_desktop_sidecar.py``
    loads this module through ``spec_from_file_location`` without registering it
    in ``sys.modules``, and ``dataclasses`` resolves ``cls.__module__`` there.
    """

    __slots__ = ("build", "requires_key")

    def __init__(
        self, build: Callable[[str, str | None], Any], requires_key: bool
    ) -> None:
        self.build = build
        self.requires_key = requires_key


DESKTOP_PROVIDERS: Mapping[str, DesktopProvider] = {
    "anthropic": DesktopProvider(build=_build_anthropic, requires_key=True),
    "openai": DesktopProvider(build=_build_openai, requires_key=True),
    "gemini": DesktopProvider(build=_build_gemini, requires_key=True),
    "openrouter": DesktopProvider(build=_build_openrouter, requires_key=True),
    "ollama": DesktopProvider(build=_build_ollama, requires_key=False),
}


def build_desktop_provider_model(
    provider: str | None, model_id: str | None, api_key: str | None
) -> Any:
    """Build the adapter for an in-app provider setting, or ``None``.

    Every failure — unknown provider, blank field, missing adapter package, a
    constructor that raises — returns ``None`` so the caller can degrade to the
    demo model. Nothing is logged and nothing is re-raised: the inputs include a
    credential, and no operator is watching this process.
    """

    from loopplane.model import ModelBoundary

    spec = DESKTOP_PROVIDERS.get((provider or "").strip())
    if spec is None:
        return None
    model_id = (model_id or "").strip()
    if not model_id:
        return None
    api_key = (api_key or "").strip() or None
    if spec.requires_key and api_key is None:
        return None

    try:
        model = spec.build(model_id, api_key)
    except Exception:
        return None
    return model if isinstance(model, ModelBoundary) else None


def select_desktop_model(env: Mapping[str, str]) -> Any:
    """Use a bounded scripted model only for an accepted packaged-smoke scenario."""

    smoke_scenario = env.get("LOOPPLANE_PACKAGED_SMOKE_SCENARIO")
    if smoke_scenario is None:
        import importlib

        from loopplane.model import ModelBoundary, TextIncrement, TokenUsage, TurnEnd

        class DemoModel:
            def __init__(self, text: str = _UNCONFIGURED_DEMO_TEXT) -> None:
                self._text = text

            def context_capacity(self) -> int:
                return 1_000_000

            async def stream_turn(self, _request: Any) -> Any:
                yield TextIncrement(text=self._text)
                yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())

        # An in-app provider setting outranks the operator-only builder
        # reference; the packaged smoke scenario above outranks both.
        provider = env.get(DESKTOP_PROVIDER_ENV)
        if (provider or "").strip():
            configured = build_desktop_provider_model(
                provider,
                env.get(DESKTOP_MODEL_ID_ENV),
                env.get(DESKTOP_API_KEY_ENV),
            )
            return (
                configured if configured is not None else DemoModel(_UNUSABLE_DEMO_TEXT)
            )

        reference = env.get("LOOPPLANE_MODEL")
        if not reference or ":" not in reference:
            return DemoModel()
        module_name, _, attr = reference.partition(":")
        try:
            builder = getattr(importlib.import_module(module_name), attr)
            model = builder()
        except Exception:
            return DemoModel()
        return model if isinstance(model, ModelBoundary) else DemoModel()
    if smoke_scenario not in _SMOKE_RESPONSES:
        raise ValueError("sidecar_smoke_scenario_invalid")

    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[TextIncrement(text=_SMOKE_RESPONSES[smoke_scenario])]
            )
        ],
        context_capacity=100_000,
    )


def main() -> None:  # pragma: no cover - real stdio entry (manual smoke)
    import os
    import sys

    import anyio

    init_line = sys.stdin.readline()
    if not init_line:
        return

    try:
        init_request = json.loads(init_line)
    except (TypeError, ValueError):
        return

    if init_request.get("method") != "initialize":
        return

    init_dispatcher = build_initialize_dispatcher()
    init_responses = anyio.run(init_dispatcher.handle_frame, init_line)  # type: ignore[attr-defined]
    if not init_responses:
        return

    sys.stdout.write(json.dumps(init_responses[0], separators=(",", ":")) + "\n")
    sys.stdout.flush()
    if "result" not in init_responses[0]:
        return

    try:
        model = select_desktop_model(os.environ)
    except ValueError:
        sys.stderr.write("sidecar smoke configuration failed\n")
        sys.exit(2)
    # The adapter holds the credential as a constructor argument and never reads
    # the environment again, so drop it here: anything this process later spawns
    # — a shell tool, a git worktree command — would otherwise inherit the key.
    os.environ.pop(DESKTOP_API_KEY_ENV, None)

    profile = Path(
        os.environ.get("LOOPPLANE_PROFILE_ROOT")
        or (Path.home() / ".loopplane" / "desktop-profile")
    )

    try:
        owner = bootstrap_desktop_owner(profile)
    except Exception as exc:
        # Fail closed before Host: public-safe one-line error then exit.
        sys.stderr.write(f"sidecar bootstrap failed: {type(exc).__name__}\n")
        sys.exit(2)

    config = desktop_runtime_config(
        model=model,
        profile_root=profile,
        generation_id=owner.generation_id,
    )
    host = owner.attach_host(config)
    profile_state = owner.ensure_profile_state()

    async def read_line() -> str | None:
        return await anyio.to_thread.run_sync(sys.stdin.readline) or None

    def write_bytes(frame: bytes) -> None:
        sys.stdout.buffer.write(frame)
        sys.stdout.buffer.flush()

    try:
        from .protocol import SerializedWriter
    except ImportError:  # pragma: no cover - script-path load
        from protocol import SerializedWriter

    writer = SerializedWriter(write_bytes)

    dispatcher = build_rpc_dispatcher(
        host,
        working_scope=profile,
        write_frame=writer.write_obj,
        profile_state=profile_state,
        mutation_lease=owner.mutation_lease,
        principal_id=profile_state.principal_id,
        runtime_config=config,
        runtime_owner=owner,
        configured_model_id=(
            (os.environ.get(DESKTOP_MODEL_ID_ENV) or "").strip() or None
        ),
    )
    dispatcher.state.initialized = True  # type: ignore[attr-defined]

    async def _run_rpc() -> None:
        try:
            await serve_rpc(dispatcher, read_line, write_frame=writer.write_obj)
        finally:
            # Release profile ownership only after every retained Host closes.
            await dispatcher.aclose()  # type: ignore[attr-defined]
            owner.release()

    anyio.run(_run_rpc)


if __name__ == "__main__":  # pragma: no cover
    main()
