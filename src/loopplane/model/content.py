"""Typed conversation content blocks (data-model.md: Content Block)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from loopplane.errors import NormalizedError


class _Block(BaseModel):
    model_config = ConfigDict(frozen=True)


class TextBlock(_Block):
    kind: Literal["text"] = "text"
    text: str


class ImageBlock(_Block):
    kind: Literal["image"] = "image"
    media: str
    format: str


OutputBlock = Annotated[TextBlock | ImageBlock, Field(discriminator="kind")]
"""What a tool invocation may yield as output (data-model.md: Tool Result)."""


class ToolCallBlock(_Block):
    kind: Literal["tool-call"] = "tool-call"
    call_id: str
    tool_name: str
    input: dict[str, object]


class ToolResultBlock(_Block):
    kind: Literal["tool-result"] = "tool-result"
    call_id: str
    outcome: Literal["success", "failure"]
    outputs: list[OutputBlock] = []
    error: NormalizedError | None = None
    artifact_reference: str | None = None


class SummaryDigest(_Block):
    """Mechanically produced compaction digest (research A6)."""

    turn_count: int
    tool_names: list[str] = []
    excerpts: list[str] = []


class SummaryMarkerBlock(_Block):
    kind: Literal["summary-marker"] = "summary-marker"
    digest: SummaryDigest


ContentBlock = Annotated[
    TextBlock | ImageBlock | ToolCallBlock | ToolResultBlock | SummaryMarkerBlock,
    Field(discriminator="kind"),
]
