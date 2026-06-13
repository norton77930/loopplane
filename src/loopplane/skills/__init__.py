"""Skills: declarative packages with execution profiles, loaded and merged
deterministically, advertised incrementally, and governed through the
Gateway (FR-050–FR-055).
"""

from loopplane.skills.adapter import SkillToolAdapter
from loopplane.skills.advertiser import DEFAULT_PROMPT_BUDGET_CHARS, SkillAdvertiser
from loopplane.skills.loader import (
    DEFAULT_SKILL_SIZE_CAP_BYTES,
    LoadedSkill,
    load_skills,
    skill_profiles,
)
from loopplane.skills.models import ExecutionProfile, Skill
from loopplane.skills.substitution import CLOSED_VARIABLES, substitute

__all__ = [
    "CLOSED_VARIABLES",
    "DEFAULT_PROMPT_BUDGET_CHARS",
    "DEFAULT_SKILL_SIZE_CAP_BYTES",
    "ExecutionProfile",
    "LoadedSkill",
    "Skill",
    "SkillAdvertiser",
    "SkillToolAdapter",
    "load_skills",
    "skill_profiles",
    "substitute",
]
