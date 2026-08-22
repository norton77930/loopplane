"""Managed workspace contexts and their session bindings.

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
    WorkspaceContext,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig


class _ContextsMixin(_CommonMixin):
    """Managed workspace contexts and their session bindings."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None

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

    def get_context(
        self, context_id: str, principal_id: str | None
    ) -> WorkspaceContext:
        contexts = self._visible_contexts(self._principal(principal_id))
        try:
            return contexts[context_id]
        except KeyError:
            raise KeyError(context_id) from None

    def list_contexts(self, principal_id: str | None) -> tuple[WorkspaceContext, ...]:
        contexts = self._visible_contexts(self._principal(principal_id))
        return tuple(contexts[key] for key in sorted(contexts))

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

    def _context_owner_actions(self) -> tuple[CapabilityAction, ...]:
        if (
            self._store is not None
            and self._config is not None
            and self._config.mutations_enabled
        ):
            return ("open", "update", "bind", "delete")
        return ("open",)

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
