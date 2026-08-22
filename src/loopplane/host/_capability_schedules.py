"""Managed schedules: durable records, enablement, and manual runs.

Split out of ``capability_manager.py`` by unit 082 T032. The method bodies
are unchanged; the attribute annotations below declare what this domain
reads off the concrete ``CapabilityManager`` so mypy checks the dependency
rather than leaving it implicit in a shared ``self``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from loopplane.host._capability_common import _CommonMixin
from loopplane.host.capabilities import (
    CapabilityAction,
    CapabilityOperationResult,
    CapabilityStatus,
    ManagedSchedule,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig


class _SchedulesMixin(_CommonMixin):
    """Managed schedules: durable records, enablement, and manual runs."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None

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

    def get_schedule(
        self, schedule_id: str, principal_id: str | None
    ) -> ManagedSchedule:
        state = self._load(self._principal(principal_id))
        if state is None or schedule_id not in state.schedules:
            raise KeyError(schedule_id)
        return self._schedule_entry(state.schedules[schedule_id])

    def list_schedules(self, principal_id: str | None) -> tuple[ManagedSchedule, ...]:
        state = self._load(self._principal(principal_id))
        if state is None:
            return ()
        return tuple(
            self._schedule_entry(record)
            for _, record in sorted(state.schedules.items())
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
