"""Managed skills: durable definitions and the provider the runtime reads.

Split out of ``capability_manager.py`` by unit 082 T032. The method bodies
are unchanged; the attribute annotations below declare what this domain
reads off the concrete ``CapabilityManager`` so mypy checks the dependency
rather than leaving it implicit in a shared ``self``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import ValidationError

from loopplane.host._capability_common import _CommonMixin
from loopplane.host.capabilities import (
    CapabilityOperationResult,
    ManagedMcpTransport,
    ManagedSkill,
    ManagedSkillDetail,
)
from loopplane.host.capability_store import (
    CapabilitySettingsState,
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)
from loopplane.host.config import CapabilityManagementConfig
from loopplane.skills import LoadedSkill, Skill

_LOCAL_PRINCIPAL = "local-default"
_UNAVAILABLE_MESSAGE = "capability settings are unavailable"
_MCP_TRANSPORTS: tuple[ManagedMcpTransport, ...] = (
    "http",
    "sse",
    "websocket",
)


class _SkillsMixin(_CommonMixin):
    """Managed skills: durable definitions and the provider the runtime reads."""

    _config: CapabilityManagementConfig | None
    _store: CapabilitySettingsStore | None
    _shared_skills: dict[str, LoadedSkill]

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

    @staticmethod
    def _invalid_skill() -> CapabilityOperationResult:
        return CapabilityOperationResult(
            ok=False,
            resource_id=None,
            status="invalid",
            message="skill is invalid",
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
