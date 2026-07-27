"""Host-owned orchestration for durable, principal-scoped capabilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast

from pydantic import ValidationError

from loopplane.adapters.mcp import MCPServerConfig, MCPToolAdapter
from loopplane.gateway import ToolGateway
from loopplane.host.capabilities import (
    CapabilityAction,
    CapabilityOperationResult,
    CapabilitySettingsStatus,
    CapabilityStatus,
    ManagedMcpConfiguration,
    ManagedMcpTransport,
    ManagedMemoryDetail,
    ManagedMemoryEntry,
    ManagedSchedule,
    ManagedSkill,
    ManagedSkillDetail,
    ModelDefault,
    WorkspaceContext,
    is_valid_managed_mcp_endpoint,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig
from loopplane.memory import (
    MemoryEntry,
    MemorySnapshotAugmentation,
    MemoryStore,
)
from loopplane.skills import LoadedSkill, Skill, SkillToolAdapter

_LOCAL_PRINCIPAL = "local-default"
_UNAVAILABLE_MESSAGE = "capability settings are unavailable"
_MCP_TRANSPORTS: tuple[ManagedMcpTransport, ...] = (
    "http",
    "sse",
    "websocket",
)


class CapabilityManager:
    """Coordinates durable settings without bypassing runtime boundaries."""

    def __init__(
        self,
        *,
        config: CapabilityManagementConfig | None,
        store: CapabilitySettingsStore | None,
        gateway: ToolGateway,
        shared_memory: MemoryStore | None = None,
        shared_skills: Mapping[str, LoadedSkill] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._gateway = gateway
        self._shared_memory = shared_memory
        self._shared_skills = dict(shared_skills or {})
        self._shared_mcp = self._discover_shared_mcp()
        self._active_mcp_ids: dict[str, set[str]] = {}

    def settings_status(
        self, principal_id: str | None = None
    ) -> CapabilitySettingsStatus:
        store = self._store
        storage_available = store is not None
        if storage_available and principal_id is not None:
            try:
                assert store is not None
                store.load(self._principal(principal_id))
            except CapabilityStoreUnavailable:
                storage_available = False
        config = self._config
        return CapabilitySettingsStatus(
            storage_available=storage_available,
            mutations_enabled=bool(config is not None and config.mutations_enabled),
            runtime_activation_enabled=bool(
                config is not None and config.runtime_activation_enabled
            ),
            mcp_endpoint_policy_available=bool(
                config is not None and config.mcp_endpoint_policy is not None
            ),
            schedule_runner_available=bool(
                config is not None and config.schedule_runner is not None
            ),
        )

    def list_memory(self, principal_id: str | None) -> tuple[ManagedMemoryEntry, ...]:
        entries: list[ManagedMemoryEntry] = []
        state = self._load(self._principal(principal_id))
        if state is not None:
            entries.extend(
                self._memory_entry(record) for _, record in sorted(state.memory.items())
            )
        if self._shared_memory is not None:
            entries.extend(
                ManagedMemoryEntry(
                    id=entry.name,
                    name=entry.name,
                    kind=entry.type,
                    description=entry.description,
                    snippet=entry.body[:160],
                    status="read_only",
                    scope="shared_read_only",
                    actions=("open",),
                )
                for entry in self._shared_memory.list_entries()
            )
        return tuple(entries)

    def get_memory(
        self, memory_id: str, principal_id: str | None
    ) -> ManagedMemoryDetail:
        state = self._load(self._principal(principal_id))
        if state is not None and memory_id in state.memory:
            record = state.memory[memory_id]
            entry = self._memory_entry(record)
            return ManagedMemoryDetail(
                **entry.__dict__,
                content=self._string(record, "content"),
            )
        if self._shared_memory is not None:
            shared = self._shared_memory.get(memory_id)
            if shared is not None:
                return ManagedMemoryDetail(
                    id=shared.name,
                    name=shared.name,
                    kind=shared.type,
                    description=shared.description,
                    snippet=shared.body[:160],
                    content="",
                    status="read_only",
                    scope="shared_read_only",
                    actions=("open",),
                )
        raise KeyError(memory_id)

    def write_memory(
        self,
        *,
        principal_id: str | None,
        name: str,
        kind: str,
        description: str,
        content: str,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        resource_id = name.strip()
        if not resource_id or not kind.strip() or not content.strip():
            return CapabilityOperationResult(
                ok=False,
                resource_id=None,
                status="invalid",
                message="memory entry is invalid",
            )
        if self._shared_memory is not None and self._shared_memory.get(resource_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=resource_id,
                status="read_only",
                message="resource name conflicts with a shared capability",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            state.memory[resource_id] = {
                "id": resource_id,
                "name": resource_id,
                "kind": kind.strip(),
                "description": description,
                "snippet": content[:160],
                "content": content,
                "status": "available",
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=resource_id,
            status="available",
            message="memory saved",
        )

    def delete_memory(
        self,
        memory_id: str,
        *,
        principal_id: str | None,
        confirm: bool,
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=memory_id,
                status="invalid",
                message="confirmation required",
            )
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        if self._shared_memory is not None and self._shared_memory.get(memory_id):
            return CapabilityOperationResult(
                ok=False,
                resource_id=memory_id,
                status="read_only",
                message="shared capability is read only",
            )
        assert self._store is not None
        deleted = False

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal deleted
            deleted = state.memory.pop(memory_id, None) is not None

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        if not deleted:
            return CapabilityOperationResult(
                ok=False,
                resource_id=memory_id,
                status="unavailable",
                message="memory entry not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=memory_id,
            status="deleted",
            message="memory deleted",
        )

    def memory_provider(
        self, principal_id: str | None
    ) -> MemorySnapshotAugmentation | None:
        if not self._activation_enabled():
            return None
        state = self._load(self._principal(principal_id))
        if state is None:
            return None
        entries = [
            MemoryEntry(
                type=self._string(record, "kind"),
                name=self._string(record, "name"),
                description=self._string(record, "description"),
                body=self._string(record, "content"),
            )
            for _, record in sorted(state.memory.items())
            if self._string(record, "name") and self._string(record, "content")
        ]
        return MemorySnapshotAugmentation(entries) if entries else None

    def list_mcp(self, principal_id: str | None) -> tuple[ManagedMcpConfiguration, ...]:
        entries: list[ManagedMcpConfiguration] = []
        state = self._load(self._principal(principal_id))
        if state is not None:
            entries.extend(
                self._mcp_entry(record)
                for name, record in sorted(state.mcp.items())
                if name not in self._shared_mcp
            )
        entries.extend(
            ManagedMcpConfiguration(
                id=name,
                name=name,
                status="connected" if tools else "unavailable",
                tool_count=len(tools),
                tools=tools,
                scope="shared_read_only",
                actions=("open",),
            )
            for name, tools in sorted(self._shared_mcp.items())
        )
        return tuple(entries)

    def get_mcp(self, mcp_id: str, principal_id: str | None) -> ManagedMcpConfiguration:
        state = self._load(self._principal(principal_id))
        if state is not None and mcp_id in state.mcp and mcp_id not in self._shared_mcp:
            return self._mcp_entry(state.mcp[mcp_id])
        tools = self._shared_mcp.get(mcp_id)
        if tools is not None:
            return ManagedMcpConfiguration(
                id=mcp_id,
                name=mcp_id,
                status="connected" if tools else "unavailable",
                tool_count=len(tools),
                tools=tools,
                scope="shared_read_only",
                actions=("open",),
            )
        raise KeyError(mcp_id)

    async def upsert_mcp(
        self,
        *,
        name: str,
        transport: str,
        url: str | None,
        command: str | None,
        args: Sequence[str],
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        del command, args
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        mcp_id = name.strip()
        endpoint = (url or "").strip()
        principal = self._principal(principal_id)
        if not mcp_id or not is_valid_managed_mcp_endpoint(transport, endpoint):
            if mcp_id:
                self._update_mcp_record(
                    principal,
                    mcp_id,
                    status="invalid",
                    problem="configuration unavailable",
                    tools=(),
                )
                await self._deactivate_mcp(principal, mcp_id)
            return CapabilityOperationResult(
                ok=False,
                resource_id=None,
                status="invalid",
                message="mcp configuration is invalid",
            )
        if mcp_id in self._shared_mcp:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="read_only",
                message="resource name conflicts with a shared capability",
            )
        normalized_transport = cast(ManagedMcpTransport, transport)
        if not self._mcp_endpoint_allowed(principal, normalized_transport, endpoint):
            self._update_mcp_record(
                principal,
                mcp_id,
                status="invalid",
                problem="configuration unavailable",
                tools=(),
            )
            await self._deactivate_mcp(principal, mcp_id)
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="invalid",
                message="mcp endpoint is not allowed",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            state.mcp[mcp_id] = {
                "id": mcp_id,
                "name": mcp_id,
                "transport": normalized_transport,
                "url": endpoint,
                "status": "disconnected",
                "tool_count": 0,
                "tools": [],
                "problem": None,
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(principal, mutate)
        except CapabilityStoreUnavailable:
            await self._deactivate_mcp(principal, mcp_id)
            return self._unavailable()
        await self._deactivate_mcp(principal, mcp_id)
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status="available",
            message="mcp configuration saved",
        )

    async def reconnect_mcp(
        self, mcp_id: str, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        return await self._connect_mcp(mcp_id, principal_id=principal_id)

    async def delete_mcp(
        self,
        mcp_id: str,
        *,
        principal_id: str | None,
        confirm: bool,
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="invalid",
                message="confirmation required",
            )
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        if mcp_id in self._shared_mcp:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="read_only",
                message="shared capability is read only",
            )
        assert self._store is not None
        principal = self._principal(principal_id)
        deleted = False

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal deleted
            deleted = state.mcp.pop(mcp_id, None) is not None

        try:
            self._store.update(principal, mutate)
        except CapabilityStoreUnavailable:
            await self._deactivate_mcp(principal, mcp_id)
            return self._unavailable()
        await self._deactivate_mcp(principal, mcp_id)
        if not deleted:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="unavailable",
                message="mcp configuration not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status="deleted",
            message="mcp configuration deleted",
        )

    def list_contexts(self, principal_id: str | None) -> tuple[WorkspaceContext, ...]:
        contexts = self._visible_contexts(self._principal(principal_id))
        return tuple(contexts[key] for key in sorted(contexts))

    def get_context(
        self, context_id: str, principal_id: str | None
    ) -> WorkspaceContext:
        contexts = self._visible_contexts(self._principal(principal_id))
        try:
            return contexts[context_id]
        except KeyError:
            raise KeyError(context_id) from None

    def upsert_context(
        self,
        *,
        name: str,
        description: str,
        workspace_label: str,
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        context_id = name.strip()
        label = workspace_label.strip()
        if not context_id or not label:
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id or None,
                status="invalid",
                message="workspace context invalid",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            state.contexts[context_id] = {
                "id": context_id,
                "name": context_id,
                "description": description,
                "workspace_label": label,
                "status": "available",
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=context_id,
            status="available",
            message="workspace context saved",
        )

    def delete_context(
        self,
        context_id: str,
        *,
        principal_id: str | None,
        confirm: bool,
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id,
                status="invalid",
                message="confirmation required",
            )
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        assert self._store is not None
        deleted = False

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal deleted
            deleted = state.contexts.pop(context_id, None) is not None

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        if not deleted:
            return CapabilityOperationResult(
                ok=False,
                resource_id=context_id,
                status="unavailable",
                message="workspace context not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=context_id,
            status="deleted",
            message="workspace context deleted",
        )

    def list_schedules(self, principal_id: str | None) -> tuple[ManagedSchedule, ...]:
        state = self._load(self._principal(principal_id))
        if state is None:
            return ()
        return tuple(
            self._schedule_entry(record)
            for _, record in sorted(state.schedules.items())
        )

    def get_schedule(
        self, schedule_id: str, principal_id: str | None
    ) -> ManagedSchedule:
        state = self._load(self._principal(principal_id))
        if state is None or schedule_id not in state.schedules:
            raise KeyError(schedule_id)
        return self._schedule_entry(state.schedules[schedule_id])

    def upsert_schedule(
        self,
        *,
        name: str,
        description: str,
        trigger: str,
        instruction: str,
        enabled: bool,
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        schedule_id = name.strip()
        normalized_trigger = trigger.strip()
        if not schedule_id or not normalized_trigger:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id or None,
                status="invalid",
                message="schedule invalid",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)
        status: CapabilityStatus = "enabled" if enabled else "disabled"

        def mutate(state: CapabilitySettingsState) -> None:
            previous = state.schedules.get(schedule_id, {})
            state.schedules[schedule_id] = {
                "id": schedule_id,
                "name": schedule_id,
                "description": description,
                "trigger": normalized_trigger,
                "instruction": instruction,
                "enabled": enabled,
                "status": status,
                "next_run_at": previous.get("next_run_at"),
                "last_run_at": previous.get("last_run_at"),
                "problem": None,
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=schedule_id,
            status=status,
            message="schedule saved",
        )

    def enable_schedule(
        self, schedule_id: str, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        return self._set_schedule_enabled(
            schedule_id,
            enabled=True,
            principal_id=principal_id,
        )

    def disable_schedule(
        self, schedule_id: str, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        return self._set_schedule_enabled(
            schedule_id,
            enabled=False,
            principal_id=principal_id,
        )

    def run_schedule_now(
        self, schedule_id: str, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        schedule = self.get_schedule(schedule_id, principal_id)
        if not schedule.enabled:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="disabled",
                message="schedule disabled",
            )
        if not schedule.instruction.strip():
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="invalid",
                message="schedule instruction is required",
            )
        runner = self._config.schedule_runner if self._config is not None else None
        if runner is None:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="unavailable",
                message="schedule runner unavailable",
            )
        principal = self._principal(principal_id)
        last_run_at = datetime.now(UTC)
        if not self._update_schedule_record(
            principal,
            schedule_id,
            status="running",
            problem=None,
            last_run_at=last_run_at,
        ):
            return self._unavailable()
        dispatched = self.get_schedule(schedule_id, principal_id)
        try:
            runner.run_now(principal, dispatched)
        except Exception:
            if not self._update_schedule_record(
                principal,
                schedule_id,
                status="failed",
                problem="dispatch unavailable",
            ):
                return self._unavailable()
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="failed",
                message="schedule run failed",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=schedule_id,
            status="running",
            message="schedule run requested",
        )

    def delete_schedule(
        self,
        schedule_id: str,
        *,
        principal_id: str | None,
        confirm: bool,
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="invalid",
                message="confirmation required",
            )
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        assert self._store is not None
        deleted = False

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal deleted
            deleted = state.schedules.pop(schedule_id, None) is not None

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        if not deleted:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="unavailable",
                message="schedule not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=schedule_id,
            status="deleted",
            message="schedule deleted",
        )

    def model_default(
        self,
        principal_id: str | None,
        *,
        available_models: Mapping[str, str] | None = None,
    ) -> ModelDefault:
        state = self._load(self._principal(principal_id))
        record = state.model_default if state is not None else None
        if record is None:
            return ModelDefault(
                model_id=None,
                label=None,
                status="fallback",
                scope="owned",
                actions=self._model_default_actions(has_default=False),
            )
        model_id = self._optional_string(record.get("model_id"))
        label = self._optional_string(record.get("label"))
        if model_id is None:
            return ModelDefault(
                model_id=None,
                label=None,
                status="fallback",
                scope="owned",
                actions=self._model_default_actions(has_default=False),
            )
        if available_models is not None and model_id not in available_models:
            return ModelDefault(
                model_id=model_id,
                label=label,
                status="fallback",
                updated_at=self._datetime(record.get("updated_at")),
                scope="owned",
                actions=self._model_default_actions(has_default=True),
                problem="model unavailable",
            )
        return ModelDefault(
            model_id=model_id,
            label=(
                available_models.get(model_id, label)
                if available_models is not None
                else label
            ),
            status="available",
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._model_default_actions(has_default=True),
            problem=None,
        )

    def set_model_default(
        self,
        model_id: str,
        *,
        available_models: Mapping[str, str],
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        if model_id not in available_models:
            return CapabilityOperationResult(
                ok=False,
                resource_id=model_id,
                status="invalid",
                message="model unavailable",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            state.model_default = {
                "model_id": model_id,
                "label": available_models[model_id],
                "status": "available",
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=model_id,
            status="available",
            message="model default saved",
        )

    def clear_model_default(
        self, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        assert self._store is not None

        def mutate(state: CapabilitySettingsState) -> None:
            state.model_default = None

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=None,
            status="fallback",
            message="model default cleared",
        )

    def list_skills(self, principal_id: str | None) -> tuple[ManagedSkill, ...]:
        entries: list[ManagedSkill] = []
        state = self._load(self._principal(principal_id))
        if state is not None:
            entries.extend(
                self._skill_entry(record)
                for name, record in sorted(state.skills.items())
                if name not in self._shared_skills
                and self._loaded_skill(record) is not None
            )
        entries.extend(
            ManagedSkill(
                id=name,
                name=name,
                description=loaded.skill.description,
                source="host",
                status="read_only",
                scope="shared_read_only",
                actions=("open",),
            )
            for name, loaded in sorted(self._shared_skills.items())
        )
        return tuple(entries)

    def get_skill(self, skill_id: str, principal_id: str | None) -> ManagedSkillDetail:
        state = self._load(self._principal(principal_id))
        if state is not None and skill_id in state.skills:
            record = state.skills[skill_id]
            loaded = self._loaded_skill(record)
            if loaded is not None and skill_id not in self._shared_skills:
                entry = self._skill_entry(record)
                return ManagedSkillDetail(
                    **entry.__dict__,
                    instructions=loaded.skill.instructions,
                )
        shared = self._shared_skills.get(skill_id)
        if shared is not None:
            return ManagedSkillDetail(
                id=skill_id,
                name=skill_id,
                description=shared.skill.description,
                source="host",
                instructions="",
                status="read_only",
                scope="shared_read_only",
                actions=("open",),
            )
        raise KeyError(skill_id)

    def write_skill(
        self,
        *,
        principal_id: str | None,
        name: str,
        description: str,
        instructions: str,
    ) -> CapabilityOperationResult:
        try:
            skill = Skill(
                name=name.strip(),
                description=description,
                instructions=instructions,
            )
        except ValidationError:
            return self._invalid_skill()
        return self._save_skill(skill, principal_id, message="skill saved")

    def import_skill(
        self,
        definition: Mapping[str, object],
        *,
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        if set(definition) - {"name", "description", "instructions", "profile"}:
            return self._invalid_skill()
        try:
            skill = Skill.model_validate(definition)
        except ValidationError:
            return self._invalid_skill()
        return self._save_skill(skill, principal_id, message="skill imported")

    def delete_skill(
        self,
        skill_id: str,
        *,
        principal_id: str | None,
        confirm: bool,
    ) -> CapabilityOperationResult:
        if not confirm:
            return CapabilityOperationResult(
                ok=False,
                resource_id=skill_id,
                status="invalid",
                message="confirmation required",
            )
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        if skill_id in self._shared_skills:
            return CapabilityOperationResult(
                ok=False,
                resource_id=skill_id,
                status="read_only",
                message="shared capability is read only",
            )
        assert self._store is not None
        deleted = False

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal deleted
            deleted = state.skills.pop(skill_id, None) is not None

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        if not deleted:
            return CapabilityOperationResult(
                ok=False,
                resource_id=skill_id,
                status="unavailable",
                message="skill not found",
            )
        return CapabilityOperationResult(
            ok=True,
            resource_id=skill_id,
            status="deleted",
            message="skill deleted",
        )

    def skills_provider(self, principal_id: str | None) -> Mapping[str, LoadedSkill]:
        if not self._activation_enabled():
            return {}
        state = self._load(self._principal(principal_id))
        if state is None:
            return {}
        loaded: dict[str, LoadedSkill] = {}
        for name, record in sorted(state.skills.items()):
            if name in self._shared_skills:
                continue
            skill = self._loaded_skill(record)
            if skill is not None:
                loaded[name] = skill
        return loaded

    async def activate_principal(self, principal_id: str | None) -> None:
        if not self._activation_enabled() or principal_id is None:
            return
        skills = self.skills_provider(principal_id)
        if skills:
            await self._gateway.replace_scoped_adapter(
                principal_id,
                "managed-skills",
                SkillToolAdapter(skills),
            )
        else:
            await self._gateway.remove_scoped_adapter(principal_id, "managed-skills")
        await self._activate_mcp(principal_id)

    async def aclose(self) -> None:
        await self._gateway.shutdown_scoped_adapters()

    async def _activate_mcp(self, principal_id: str) -> None:
        state = self._load(principal_id)
        if state is None:
            return
        active = self._active_mcp_ids.setdefault(principal_id, set())
        configured = set(state.mcp)
        for mcp_id in sorted(active - configured):
            await self._deactivate_mcp(principal_id, mcp_id)
        for mcp_id, record in sorted(state.mcp.items()):
            status = self._string(record, "status")
            if status == "connected":
                await self._connect_mcp(
                    mcp_id,
                    principal_id=principal_id,
                )
            else:
                await self._deactivate_mcp(principal_id, mcp_id)

    async def _connect_mcp(
        self,
        mcp_id: str,
        *,
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        if mcp_id in self._shared_mcp:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="read_only",
                message="shared capability is read only",
            )
        principal = self._principal(principal_id)
        state = self._load(principal)
        if state is None or mcp_id not in state.mcp:
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="unavailable",
                message="mcp configuration not found",
            )
        record = state.mcp[mcp_id]
        transport_value = self._string(record, "transport")
        endpoint = self._string(record, "url")
        if not is_valid_managed_mcp_endpoint(transport_value, endpoint):
            self._update_mcp_record(
                principal,
                mcp_id,
                status="invalid",
                problem="configuration unavailable",
                tools=(),
            )
            await self._deactivate_mcp(principal, mcp_id)
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="invalid",
                message="mcp configuration is invalid",
            )
        transport = cast(ManagedMcpTransport, transport_value)
        if not self._mcp_endpoint_allowed(principal, transport, endpoint):
            self._update_mcp_record(
                principal,
                mcp_id,
                status="invalid",
                problem="configuration unavailable",
                tools=(),
            )
            await self._deactivate_mcp(principal, mcp_id)
            return CapabilityOperationResult(
                ok=False,
                resource_id=mcp_id,
                status="invalid",
                message="mcp endpoint is not allowed",
            )

        try:
            candidate = MCPToolAdapter(
                [
                    MCPServerConfig(
                        name=mcp_id,
                        transport=transport,
                        url=endpoint,
                    )
                ]
            )
            await candidate.connect()
            failures = candidate.connection_failures
            descriptors = tuple(candidate.describe())
        except Exception:
            candidate_value = locals().get("candidate")
            if isinstance(candidate_value, MCPToolAdapter):
                await self._shutdown_mcp_candidate(candidate_value)
            return await self._mcp_failure(principal, mcp_id)
        if failures:
            await self._shutdown_mcp_candidate(candidate)
            return await self._mcp_failure(principal, mcp_id)

        tools = tuple(sorted(descriptor.name for descriptor in descriptors))
        if not self._update_mcp_record(
            principal,
            mcp_id,
            status="connected",
            problem=None,
            tools=tools,
        ):
            await self._shutdown_mcp_candidate(candidate)
            await self._deactivate_mcp(principal, mcp_id)
            return self._unavailable()

        if self._activation_enabled() and principal_id is not None:
            try:
                await self._gateway.replace_scoped_adapter(
                    principal_id,
                    self._mcp_adapter_id(mcp_id),
                    candidate,
                )
            except Exception:
                await self._shutdown_mcp_candidate(candidate)
                return await self._mcp_failure(principal, mcp_id)
            self._active_mcp_ids.setdefault(principal_id, set()).add(mcp_id)
        else:
            await self._shutdown_mcp_candidate(candidate)
        return CapabilityOperationResult(
            ok=True,
            resource_id=mcp_id,
            status="connected",
            message="mcp reconnected",
        )

    async def _mcp_failure(
        self, principal_id: str, mcp_id: str
    ) -> CapabilityOperationResult:
        updated = self._update_mcp_record(
            principal_id,
            mcp_id,
            status="failed",
            problem="connection unavailable",
            tools=(),
        )
        await self._deactivate_mcp(principal_id, mcp_id)
        if not updated:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=False,
            resource_id=mcp_id,
            status="failed",
            message="mcp reconnect failed",
        )

    async def _deactivate_mcp(self, principal_id: str, mcp_id: str) -> None:
        try:
            await self._gateway.remove_scoped_adapter(
                principal_id, self._mcp_adapter_id(mcp_id)
            )
        finally:
            active = self._active_mcp_ids.get(principal_id)
            if active is not None:
                active.discard(mcp_id)
                if not active:
                    self._active_mcp_ids.pop(principal_id, None)

    def _update_mcp_record(
        self,
        principal_id: str,
        mcp_id: str,
        *,
        status: CapabilityStatus,
        problem: str | None,
        tools: Sequence[str] | None = None,
    ) -> bool:
        if self._store is None:
            return False
        updated = False
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal updated
            record = state.mcp.get(mcp_id)
            if record is None:
                return
            record["status"] = status
            record["problem"] = problem
            record["updated_at"] = timestamp.isoformat()
            if tools is not None:
                record["tools"] = list(tools)
                record["tool_count"] = len(tools)
            updated = True

        try:
            self._store.update(principal_id, mutate)
        except CapabilityStoreUnavailable:
            return False
        return updated

    def _mcp_endpoint_allowed(
        self,
        principal_id: str,
        transport: ManagedMcpTransport,
        endpoint: str,
    ) -> bool:
        policy = self._config.mcp_endpoint_policy if self._config is not None else None
        if policy is None:
            return False
        try:
            return bool(policy(principal_id, transport, endpoint))
        except Exception:
            return False

    @staticmethod
    async def _shutdown_mcp_candidate(candidate: MCPToolAdapter) -> None:
        try:
            await candidate.shutdown()
        except Exception:
            pass

    @staticmethod
    def _mcp_adapter_id(mcp_id: str) -> str:
        return f"managed-mcp:{mcp_id}"

    def _set_schedule_enabled(
        self,
        schedule_id: str,
        *,
        enabled: bool,
        principal_id: str | None,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        principal = self._principal(principal_id)
        state = self._load(principal)
        if state is None or schedule_id not in state.schedules:
            return CapabilityOperationResult(
                ok=False,
                resource_id=schedule_id,
                status="unavailable",
                message="schedule not found",
            )
        status: CapabilityStatus = "enabled" if enabled else "disabled"
        if not self._update_schedule_record(
            principal,
            schedule_id,
            status=status,
            problem=None,
            enabled=enabled,
        ):
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=schedule_id,
            status=status,
            message="schedule enabled" if enabled else "schedule disabled",
        )

    def _update_schedule_record(
        self,
        principal_id: str,
        schedule_id: str,
        *,
        status: CapabilityStatus,
        problem: str | None,
        enabled: bool | None = None,
        last_run_at: datetime | None = None,
    ) -> bool:
        if self._store is None:
            return False
        updated = False
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            nonlocal updated
            record = state.schedules.get(schedule_id)
            if record is None:
                return
            record["status"] = status
            record["problem"] = problem
            record["updated_at"] = timestamp.isoformat()
            if enabled is not None:
                record["enabled"] = enabled
            if last_run_at is not None:
                record["last_run_at"] = last_run_at.isoformat()
            updated = True

        try:
            self._store.update(principal_id, mutate)
        except CapabilityStoreUnavailable:
            return False
        return updated

    def _save_skill(
        self,
        skill: Skill,
        principal_id: str | None,
        *,
        message: str,
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        name = skill.name.strip()
        if not name or not skill.instructions.strip():
            return self._invalid_skill()
        if name in self._shared_skills:
            return CapabilityOperationResult(
                ok=False,
                resource_id=name,
                status="read_only",
                message="resource name conflicts with a shared capability",
            )
        assert self._store is not None
        timestamp = datetime.now(UTC)

        def mutate(state: CapabilitySettingsState) -> None:
            state.skills[name] = {
                "id": name,
                "name": name,
                "description": skill.description,
                "source": "managed",
                "status": "available",
                "definition": skill.model_dump(mode="json"),
                "updated_at": timestamp.isoformat(),
            }

        try:
            self._store.update(self._principal(principal_id), mutate)
        except CapabilityStoreUnavailable:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=True,
            resource_id=name,
            status="available",
            message=message,
        )

    def _mutation_refusal(self) -> CapabilityOperationResult | None:
        if self._config is None or not self._config.mutations_enabled:
            return CapabilityOperationResult(
                ok=False,
                resource_id=None,
                status="disabled_by_policy",
                message="capability mutations are disabled",
            )
        if self._store is None:
            return self._unavailable()
        return None

    def _activation_enabled(self) -> bool:
        return bool(
            self._config is not None and self._config.runtime_activation_enabled
        )

    def _load(self, principal_id: str) -> CapabilitySettingsState | None:
        if self._store is None:
            return None
        try:
            return self._store.load(principal_id)
        except CapabilityStoreUnavailable:
            return None

    def _discover_shared_mcp(self) -> dict[str, tuple[str, ...]]:
        discovered: dict[str, list[str]] = {}
        for descriptor in self._gateway.descriptors():
            source = descriptor.source
            if not source.startswith("external-server:"):
                continue
            server_name = source.removeprefix("external-server:")
            if server_name:
                discovered.setdefault(server_name, []).append(descriptor.name)
        return {
            name: tuple(sorted(tools)) for name, tools in sorted(discovered.items())
        }

    def _owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "delete")
        return ("open",)

    def _mcp_owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "reconnect", "delete")
        return ("open",)

    def _context_owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "bind", "delete")
        return ("open",)

    def _schedule_owner_actions(self, *, enabled: bool) -> tuple[CapabilityAction, ...]:
        if (
            self._store is None
            or self._config is None
            or not self._config.mutations_enabled
        ):
            return ("open",)
        if enabled:
            return ("open", "update", "disable", "run_now", "delete")
        return ("open", "update", "enable", "delete")

    def _model_default_actions(
        self, *, has_default: bool
    ) -> tuple[CapabilityAction, ...]:
        if (
            self._store is None
            or self._config is None
            or not self._config.mutations_enabled
        ):
            return ()
        return ("set", "clear") if has_default else ("set",)

    def _memory_entry(self, record: Mapping[str, object]) -> ManagedMemoryEntry:
        return ManagedMemoryEntry(
            id=self._string(record, "id"),
            name=self._string(record, "name"),
            kind=self._string(record, "kind"),
            description=self._string(record, "description"),
            snippet=self._string(record, "snippet"),
            status="available",
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._owner_actions(),
            problem=None,
        )

    def _skill_entry(self, record: Mapping[str, object]) -> ManagedSkill:
        return ManagedSkill(
            id=self._string(record, "id"),
            name=self._string(record, "name"),
            description=self._string(record, "description"),
            source="managed",
            status="available",
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._owner_actions(),
            problem=None,
        )

    def _mcp_entry(self, record: Mapping[str, object]) -> ManagedMcpConfiguration:
        transport_value = self._string(record, "transport")
        transport = transport_value if transport_value in _MCP_TRANSPORTS else None
        status_value = self._string(record, "status")
        status = cast(
            CapabilityStatus,
            status_value
            if status_value in {"connected", "disconnected", "failed", "unavailable"}
            else "unavailable",
        )
        tools = self._string_sequence(record.get("tools"))
        return ManagedMcpConfiguration(
            id=self._string(record, "id"),
            name=self._string(record, "name"),
            status=status,
            tool_count=len(tools),
            transport=transport,
            url=self._optional_string(record.get("url")),
            tools=tools,
            problem=self._optional_string(record.get("problem")),
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._mcp_owner_actions(),
        )

    def _visible_contexts(self, principal_id: str) -> dict[str, WorkspaceContext]:
        state = self._load(principal_id)
        owned = (
            {
                context_id: self._context_entry(record)
                for context_id, record in state.contexts.items()
            }
            if state is not None
            else {}
        )
        provider = (
            self._config.allowed_context_provider if self._config is not None else None
        )
        if provider is None:
            return owned
        try:
            provided = tuple(provider(principal_id))
        except Exception:
            return owned

        by_id: dict[str, list[WorkspaceContext]] = {}
        for context in provided:
            if not isinstance(context, WorkspaceContext):
                continue
            if (
                not isinstance(context.id, str)
                or not context.id.strip()
                or not isinstance(context.name, str)
                or not context.name.strip()
                or not isinstance(context.description, str)
                or not isinstance(context.workspace_label, str)
                or not context.workspace_label.strip()
            ):
                continue
            by_id.setdefault(context.id, []).append(context)

        collisions = set(owned) & set(by_id)
        collisions.update(
            context_id for context_id, items in by_id.items() if len(items) != 1
        )
        for context_id in collisions:
            owned.pop(context_id, None)

        actions: tuple[CapabilityAction, ...] = (
            ("open", "bind")
            if self._config is not None and self._config.mutations_enabled
            else ("open",)
        )
        for context_id, items in by_id.items():
            if context_id in collisions or len(items) != 1:
                continue
            context = items[0]
            owned[context_id] = WorkspaceContext(
                id=context.id,
                name=context.name,
                description=context.description,
                workspace_label=context.workspace_label,
                status="read_only",
                updated_at=(
                    context.updated_at
                    if isinstance(context.updated_at, datetime)
                    else None
                ),
                owner_id=None,
                scope="shared_read_only",
                actions=actions,
                problem=None,
            )
        return owned

    def _context_entry(self, record: Mapping[str, object]) -> WorkspaceContext:
        return WorkspaceContext(
            id=self._string(record, "id"),
            name=self._string(record, "name"),
            description=self._string(record, "description"),
            workspace_label=self._string(record, "workspace_label"),
            status="available",
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._context_owner_actions(),
            problem=None,
        )

    def _schedule_entry(self, record: Mapping[str, object]) -> ManagedSchedule:
        enabled = record.get("enabled") is True
        status_value = self._string(record, "status")
        status = cast(
            CapabilityStatus,
            status_value
            if status_value in {"disabled", "enabled", "failed", "running"}
            else ("enabled" if enabled else "disabled"),
        )
        return ManagedSchedule(
            id=self._string(record, "id"),
            name=self._string(record, "name"),
            description=self._string(record, "description"),
            trigger=self._string(record, "trigger"),
            enabled=enabled,
            instruction=self._string(record, "instruction"),
            status=status,
            next_run_at=self._datetime(record.get("next_run_at")),
            last_run_at=self._datetime(record.get("last_run_at")),
            problem=self._optional_string(record.get("problem")),
            updated_at=self._datetime(record.get("updated_at")),
            scope="owned",
            actions=self._schedule_owner_actions(enabled=enabled),
        )

    @staticmethod
    def _loaded_skill(record: Mapping[str, object]) -> LoadedSkill | None:
        definition = record.get("definition")
        if not isinstance(definition, Mapping):
            return None
        try:
            skill = Skill.model_validate(dict(definition))
        except ValidationError:
            return None
        return LoadedSkill(skill=skill, source="managed")

    @staticmethod
    def _string(record: Mapping[str, object], key: str) -> str:
        value = record.get(key, "")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _string_sequence(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, str))

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _principal(principal_id: str | None) -> str:
        return principal_id or _LOCAL_PRINCIPAL

    @staticmethod
    def _unavailable() -> CapabilityOperationResult:
        return CapabilityOperationResult(
            ok=False,
            resource_id=None,
            status="unavailable",
            message=_UNAVAILABLE_MESSAGE,
        )

    @staticmethod
    def _invalid_skill() -> CapabilityOperationResult:
        return CapabilityOperationResult(
            ok=False,
            resource_id=None,
            status="invalid",
            message="skill is invalid",
        )
