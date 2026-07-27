from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from loopplane.checkpoint import FileCheckpointStore
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.model import ModelIncrement, ModelRequest, TextBlock, TextIncrement
from loopplane.skills import LoadedSkill, Skill

pytestmark = pytest.mark.anyio


async def _discard(_event: RuntimeEvent) -> None:
    return None


class _RecordingModel:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.requests.append(request)
        yield TextIncrement(text="ok")


class _StaticAugmentation:
    def __init__(self, text: str) -> None:
        self._text = text

    def augment_for(self, _prompt: str) -> str:
        return self._text

    def re_establish(self) -> None:
        return None


def _augmentation_text(request: ModelRequest) -> str:
    first = request.context[0]
    return "".join(block.text for block in first.blocks if isinstance(block, TextBlock))


async def test_session_assembly_uses_principal_scoped_memory_and_skills(
    tmp_path: Path,
) -> None:
    model = _RecordingModel()
    seen_memory_principals: list[str | None] = []
    seen_skill_principals: list[str | None] = []

    def memory_provider(principal_id: str | None) -> _StaticAugmentation | None:
        seen_memory_principals.append(principal_id)
        if principal_id != "owner":
            return None
        return _StaticAugmentation("[owner memory] private deployment note")

    def skills_provider(
        principal_id: str | None,
    ) -> dict[str, LoadedSkill]:
        seen_skill_principals.append(principal_id)
        if principal_id != "owner":
            return {}
        return {
            "owner-skill": LoadedSkill(
                skill=Skill(
                    name="owner-skill",
                    description="owner only",
                    instructions="use owner data",
                ),
                source="managed",
            )
        }

    controller = RuntimeController(
        model=model,
        gateway=ToolGateway(),
        event_sink=_discard,
        scoped_memory_provider=memory_provider,
        scoped_skills_provider=skills_provider,
    )
    owner_session = controller.create_session(
        working_scope=tmp_path,
        principal_id="owner",
    )
    other_session = controller.create_session(
        working_scope=tmp_path,
        principal_id="other",
    )

    await controller.drive(owner_session, [TextBlock(text="deploy")])
    await controller.drive(other_session, [TextBlock(text="deploy")])

    owner_prompt, other_prompt = map(_augmentation_text, model.requests)
    assert "private deployment note" in owner_prompt
    assert "skill:owner-skill" in owner_prompt
    assert "private deployment note" not in other_prompt
    assert "skill:owner-skill" not in other_prompt
    assert seen_memory_principals == ["owner", "other"]
    assert seen_skill_principals == ["owner", "other"]


async def test_set_session_context_checks_owner_and_updates_durable_metadata(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(
        model=_RecordingModel(),
        gateway=ToolGateway(),
        event_sink=_discard,
        checkpoint_store=FileCheckpointStore(tmp_path / "sessions"),
    )
    session_id = controller.create_session(
        working_scope=tmp_path,
        principal_id="owner",
    )

    await controller.set_session_context(
        session_id,
        principal_id="owner",
        context_id="docs",
        context_name="Docs",
        context_workspace_label="docs-repo",
        context_status="ready",
    )

    [summary] = controller.list_sessions()
    assert summary.context_id == "docs"
    assert summary.context_name == "Docs"
    assert summary.context_workspace_label == "docs-repo"
    assert summary.context_status == "ready"

    with pytest.raises(KeyError):
        await controller.set_session_context(
            session_id,
            principal_id="other",
            context_id="private",
            context_name="Private",
            context_workspace_label=None,
            context_status="ready",
        )
