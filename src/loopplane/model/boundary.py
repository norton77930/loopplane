"""The model boundary: the loop's single model-facing seam
(contracts/model-boundary.md).

Deliberately minimal: provider integrations are not a phase-1 deliverable.
The boundary exists so the loop has exactly one model-facing interface and so
tests can substitute it completely.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from loopplane.model.content import ContentBlock


class _Shape(BaseModel):
    model_config = ConfigDict(frozen=True)


class TokenUsage(_Shape):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0


class GenerationLimits(_Shape):
    max_output_tokens: int | None = None


class Message(_Shape):
    """One entry of the assembled context handed to the model."""

    role: Literal["user", "assistant"]
    blocks: list[ContentBlock]


class ToolDescriptor(_Shape):
    """The registered identity of a tool (data-model.md: Tool Descriptor)."""

    name: str
    description: str
    input_schema: dict[str, object]
    concurrency_safe: bool = False
    read_only: bool = False
    source: str = "internal"


class ModelRequest(_Shape):
    context: list[Message]
    tools: list[ToolDescriptor] = []
    limits: GenerationLimits = GenerationLimits()


class TextIncrement(_Shape):
    text: str


class ReasoningIncrement(_Shape):
    text: str


class ToolCallRequest(_Shape):
    """A tool-call request as the model emitted it; the input is raw and is
    validated later by the Gateway.
    """

    call_id: str
    tool_name: str
    input: dict[str, object]


class TurnEnd(_Shape):
    stop_reason: str
    usage: TokenUsage


ModelIncrement = TextIncrement | ReasoningIncrement | ToolCallRequest | TurnEnd


class ContextOverflowError(Exception):
    """Distinct signal: the assembled context exceeds the model's capacity,
    so the loop can compact and retry exactly once (FR-008).
    """


@runtime_checkable
class ModelBoundary(Protocol):
    def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]: ...

    def context_capacity(self) -> int: ...
