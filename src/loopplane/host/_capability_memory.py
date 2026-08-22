"""Managed memory entries and the shared store they project onto.

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
    CapabilityOperationResult,
    ManagedMemoryDetail,
    ManagedMemoryEntry,
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


class _MemoryMixin(_CommonMixin):
    """Managed memory entries and the shared store they project onto."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None
    _shared_memory: MemoryStore | None

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
