"""Skills behind the Gateway adapter SPI: invoking `skill:{name}` returns
the skill's instructions with closed-list variables substituted (FR-054,
FR-055). Every invocation traverses the full Gateway pipeline, where the
Human Approval boundary honors the execution profile.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.skills.loader import LoadedSkill
from loopplane.skills.substitution import substitute

_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"arguments": {"type": "string"}},
    "additionalProperties": False,
}


class SkillToolAdapter:
    def __init__(self, skills: Mapping[str, LoadedSkill]) -> None:
        self._skills = {name: loaded.skill for name, loaded in skills.items()}

    def describe(self) -> Sequence[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=f"skill:{name}",
                description=self._skills[name].description,
                input_schema=dict(_INPUT_SCHEMA),
                concurrency_safe=True,
                read_only=True,
            )
            for name in sorted(self._skills)
        ]

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        skill = self._skills[name.removeprefix("skill:")]
        values = {
            "session_id": context.session_id,
            "working_scope": str(context.working_scope),
            "arguments": str(call_input.get("arguments", "")),
        }
        yield TextBlock(text=substitute(skill.instructions, values))

    async def shutdown(self) -> None:
        return None
