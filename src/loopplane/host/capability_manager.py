from __future__ import annotations

from collections.abc import Mapping

from loopplane.gateway import ToolGateway
from loopplane.host._capability_contexts import _ContextsMixin
from loopplane.host._capability_mcp import _McpMixin
from loopplane.host._capability_memory import _MemoryMixin
from loopplane.host._capability_model import _ModelMixin
from loopplane.host._capability_schedules import _SchedulesMixin
from loopplane.host._capability_skills import _SkillsMixin
from loopplane.host.capabilities import (
    CapabilitySettingsStatus,
    ManagedMcpTransport,
)
from loopplane.host.capability_store import (
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig
from loopplane.memory import (
    MemoryStore,
)
from loopplane.skills import LoadedSkill, SkillToolAdapter

_LOCAL_PRINCIPAL = "local-default"
_UNAVAILABLE_MESSAGE = "capability settings are unavailable"
_MCP_TRANSPORTS: tuple[ManagedMcpTransport, ...] = (
    "http",
    "sse",
    "websocket",
)


class CapabilityManager(
    _McpMixin, _SkillsMixin, _MemoryMixin, _SchedulesMixin, _ContextsMixin, _ModelMixin
):
    """Coordinates durable settings without bypassing runtime boundaries.

    The per-domain behaviour lives in the mixins above, one module each;
    what stays here is construction and the lifecycle that spans domains.
    """

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
