"""Primitives every capability domain shares.

Split out of ``capability_manager.py`` by unit 082 T032. The method bodies
are unchanged; the attribute annotations below declare what this domain
reads off the concrete ``CapabilityManager`` so mypy checks the dependency
rather than leaving it implicit in a shared ``self``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from loopplane.host.capabilities import (
    CapabilityAction,
    CapabilityOperationResult,
    ManagedMcpTransport,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig

_LOCAL_PRINCIPAL = "local-default"
_UNAVAILABLE_MESSAGE = "capability settings are unavailable"
_MCP_TRANSPORTS: tuple[ManagedMcpTransport, ...] = (
    "http",
    "sse",
    "websocket",
)


class _CommonMixin:
    """Primitives every capability domain shares."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None

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

    def _owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "delete")
        return ("open",)

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
