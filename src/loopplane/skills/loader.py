"""Skill loading and deterministic merge (FR-051, FR-052): sources are
ordered broadest first and the more specific source wins on name conflicts;
a malformed or oversize skill is skipped with a problem report — never
crashed on, never partially loaded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from loopplane.skills.models import ExecutionProfile, Skill

DEFAULT_SKILL_SIZE_CAP_BYTES = 32 * 1024


@dataclass(frozen=True)
class LoadedSkill:
    skill: Skill
    source: str


def load_skills(
    sources: Sequence[Path], *, size_cap_bytes: int = DEFAULT_SKILL_SIZE_CAP_BYTES
) -> tuple[dict[str, LoadedSkill], list[str]]:
    loaded: dict[str, LoadedSkill] = {}
    problems: list[str] = []
    for source in sources:
        if not source.is_dir():
            continue
        for path in sorted(source.glob("*.json")):
            try:
                raw = path.read_bytes()
            except OSError as exc:
                problems.append(f"skill file {path.name} is unreadable: {exc}")
                continue
            if len(raw) > size_cap_bytes:
                problems.append(
                    f"skill file {path.name} exceeds the {size_cap_bytes}-byte "
                    f"size cap and was skipped"
                )
                continue
            try:
                skill = Skill.model_validate_json(raw)
            except ValidationError:
                problems.append(f"skill file {path.name} is malformed and was skipped")
                continue
            loaded[skill.name] = LoadedSkill(skill=skill, source=str(source))
    return loaded, problems


def skill_profiles(loaded: Mapping[str, LoadedSkill]) -> dict[str, ExecutionProfile]:
    """Map loaded skills to their Gateway tool names for the Human Approval
    boundary (FR-055).
    """
    return {
        f"skill:{name}": loaded_skill.skill.profile
        for name, loaded_skill in loaded.items()
    }
