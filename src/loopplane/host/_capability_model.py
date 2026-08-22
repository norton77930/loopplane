"""The durable per-principal model default.

Split out of ``capability_manager.py`` by unit 082 T032. The method bodies
are unchanged; the attribute annotations below declare what this domain
reads off the concrete ``CapabilityManager`` so mypy checks the dependency
rather than leaving it implicit in a shared ``self``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from loopplane.host._capability_common import _CommonMixin
from loopplane.host.capabilities import (
    CapabilityAction,
    CapabilityOperationResult,
    ManagedMcpTransport,
    ModelDefault,
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


class _ModelMixin(_CommonMixin):
    """The durable per-principal model default."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None

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
