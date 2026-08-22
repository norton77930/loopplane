"""Managed MCP servers: durable configuration and live gateway adapters.

Split out of ``capability_manager.py`` by unit 082 T032. The method bodies
are unchanged; the attribute annotations below declare what this domain
reads off the concrete ``CapabilityManager`` so mypy checks the dependency
rather than leaving it implicit in a shared ``self``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast

from loopplane.adapters.mcp import MCPServerConfig, MCPToolAdapter
from loopplane.gateway import ToolGateway
from loopplane.host._capability_common import _CommonMixin
from loopplane.host.capabilities import (
    CapabilityAction,
    CapabilityOperationResult,
    CapabilityStatus,
    ManagedMcpAuthorization,
    ManagedMcpConfiguration,
    ManagedMcpTransport,
    is_valid_managed_mcp_endpoint,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig

_MCP_TRANSPORTS: tuple[ManagedMcpTransport, ...] = (
    "http",
    "sse",
    "websocket",
)

# 084 — the transports that can carry interactive authorization. websocket cannot:
# the SDK's client accepts neither headers nor an auth handler (ADR 0007 D3).
_MCP_AUTH: tuple[ManagedMcpTransport, ...] = ("http", "sse")


class _McpMixin(_CommonMixin):
    """Managed MCP servers: durable configuration and live gateway adapters."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None
    _gateway: ToolGateway
    _shared_mcp: dict[str, tuple[str, ...]]
    _active_mcp_ids: dict[str, set[str]]

    async def upsert_mcp(
        self,
        *,
        name: str,
        transport: str,
        url: str | None,
        command: str | None,
        args: Sequence[str],
        principal_id: str | None,
        authorization: str | None = None,
    ) -> CapabilityOperationResult:
        del command, args
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        mcp_id = name.strip()
        endpoint = (url or "").strip()
        principal = self._principal(principal_id)
        # 084 — a mode, never a credential. Anything but the one known mode (or
        # nothing) is a configuration error, not a value to store and puzzle over
        # later; and interactive authorization has no meaning on websocket.
        mode = (authorization or "").strip() or None
        if mode is not None and (mode != "interactive" or transport not in _MCP_AUTH):
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
                resource_id=mcp_id or None,
                status="invalid",
                message="mcp configuration is invalid",
            )
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
                # 084 — a server that authorizes a person starts out unauthorized
                # rather than merely disconnected, so the surface can say which of
                # the two it is without holding any material to check.
                "status": "needs_authorization" if mode else "disconnected",
                "tool_count": 0,
                "tools": [],
                "problem": None,
                # Persisted as "auth_mode", not "authorization": the settings store
                # rejects credential-shaped keys outright (_FORBIDDEN_KEY_PARTS),
                # because this document lives in the profile root and reaches
                # backups. That guard is right; the field name moves, not the guard.
                "auth_mode": mode,
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

    async def reconnect_mcp(
        self, mcp_id: str, *, principal_id: str | None
    ) -> CapabilityOperationResult:
        refusal = self._mutation_refusal()
        if refusal is not None:
            return refusal
        return await self._connect_mcp(mcp_id, principal_id=principal_id)

    def _mcp_entry(self, record: Mapping[str, object]) -> ManagedMcpConfiguration:
        transport_value = self._string(record, "transport")
        transport = transport_value if transport_value in _MCP_TRANSPORTS else None
        status_value = self._string(record, "status")
        status = cast(
            CapabilityStatus,
            status_value
            if status_value
            in {
                "connected",
                "disconnected",
                "failed",
                "needs_authorization",
                "unavailable",
            }
            else "unavailable",
        )
        # 084 — the mode round-trips; material never does, because none is stored.
        authorization_value = self._optional_string(record.get("auth_mode"))
        authorization = cast(
            "ManagedMcpAuthorization | None",
            authorization_value if authorization_value == "interactive" else None,
        )
        tools = self._string_sequence(record.get("tools"))
        return ManagedMcpConfiguration(
            authorization=authorization,
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

    def _mcp_owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "reconnect", "delete")
        return ("open",)

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

        # 084 — the stored mode decides whether this connection authorizes a person.
        stored = self._load(principal)
        record = (stored.mcp.get(mcp_id) if stored is not None else None) or {}
        mode = self._optional_string(record.get("auth_mode"))
        interactive = mode == "interactive"
        config = self._config

        # The seams are the host's collaborators, passed straight through — but only
        # for a server that actually authorizes a person. An ordinary server is
        # constructed with exactly the arguments it was before 084, which is what
        # makes "default-unused is byte-identical" true at this call site and not
        # merely in the adapter's behaviour (FR-016). When the seams are absent and
        # the server needs them, the adapter fails closed on its own; this layer
        # does not second-guess it.
        seams: dict[str, object] = {}
        if interactive:
            seams = {
                "authorization_handler": (
                    config.mcp_authorization_handler if config is not None else None
                ),
                "token_store": config.mcp_token_store if config is not None else None,
                "principal_id": principal,
            }

        try:
            candidate = MCPToolAdapter(
                [
                    MCPServerConfig(
                        name=mcp_id,
                        transport=transport,
                        url=endpoint,
                        authorization="interactive" if interactive else None,
                    )
                ],
                **seams,  # type: ignore[arg-type]
            )
            await candidate.connect()
            failures = candidate.connection_failures
            descriptors = tuple(candidate.describe())
        except Exception:
            candidate_value = locals().get("candidate")
            if isinstance(candidate_value, MCPToolAdapter):
                await self._shutdown_mcp_candidate(candidate_value)
            return await self._mcp_failure(principal, mcp_id, interactive=interactive)
        if failures:
            await self._shutdown_mcp_candidate(candidate)
            return await self._mcp_failure(principal, mcp_id, interactive=interactive)

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

    @staticmethod
    def _mcp_adapter_id(mcp_id: str) -> str:
        return f"managed-mcp:{mcp_id}"

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

    async def _mcp_failure(
        self, principal_id: str, mcp_id: str, *, interactive: bool = False
    ) -> CapabilityOperationResult:
        # 084 — an interactive server that will not connect is, from the operator's
        # side, a thing to authorize rather than a thing that is broken. Saying
        # "failed" would send them looking for a misconfiguration that is not there.
        # The distinction costs no material: it comes from the stored mode.
        status: CapabilityStatus = "needs_authorization" if interactive else "failed"
        updated = self._update_mcp_record(
            principal_id,
            mcp_id,
            status=status,
            problem=(
                "authorization required" if interactive else "connection unavailable"
            ),
            tools=(),
        )
        await self._deactivate_mcp(principal_id, mcp_id)
        if not updated:
            return self._unavailable()
        return CapabilityOperationResult(
            ok=False,
            resource_id=mcp_id,
            status=status,
            message=(
                "mcp needs authorization" if interactive else "mcp reconnect failed"
            ),
        )

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

    @staticmethod
    async def _shutdown_mcp_candidate(candidate: MCPToolAdapter) -> None:
        try:
            await candidate.shutdown()
        except Exception:
            pass

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
