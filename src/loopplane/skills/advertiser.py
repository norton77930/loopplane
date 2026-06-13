"""Incremental skill advertisement within a bounded prompt budget (FR-053).

Each skill is advertised to the model once per session; later turns
advertise only what is newly available. After compaction, already-advertised
skills are re-established without being treated as newly available and
without double-counting against the budget.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from loopplane.skills.loader import LoadedSkill
from loopplane.skills.models import Skill

DEFAULT_PROMPT_BUDGET_CHARS = 2000


def _render(skill: Skill) -> str:
    return f"[skill available] skill:{skill.name} — {skill.description}"


class SkillAdvertiser:
    def __init__(
        self,
        skills: Mapping[str, LoadedSkill] | Iterable[Skill],
        *,
        prompt_budget_chars: int = DEFAULT_PROMPT_BUDGET_CHARS,
    ) -> None:
        if isinstance(skills, Mapping):
            items = [loaded.skill for loaded in skills.values()]
        else:
            items = list(skills)
        self._skills = sorted(items, key=lambda skill: skill.name)
        self._budget = prompt_budget_chars
        self._advertised: set[str] = set()

    def augment_for(self, prompt: str) -> str | None:
        """The next batch of not-yet-advertised skills, bounded by this
        turn's prompt budget; what does not fit waits for a later turn.
        """
        lines: list[str] = []
        spent = 0
        for skill in self._skills:
            if skill.name in self._advertised:
                continue
            line = _render(skill)
            if spent + len(line) > self._budget:
                break
            lines.append(line)
            spent += len(line)
            self._advertised.add(skill.name)
        if not lines:
            return None
        return "\n".join(lines)

    def re_establish(self) -> str | None:
        """Repeat everything already advertised — not newly available, not
        counted against the budget (FR-053).
        """
        lines = [
            _render(skill) for skill in self._skills if skill.name in self._advertised
        ]
        if not lines:
            return None
        return "\n".join(lines)
