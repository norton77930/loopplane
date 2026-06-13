"""The adapter SPI: a tool source provides exactly three capabilities —
describe, invoke, shutdown (contracts/tool-gateway.md).

Adapters never see policy, timeouts, size management, or event emission;
those belong to the Gateway.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import ImageBlock, TextBlock


class ErrorOutput(BaseModel):
    """An error output marks the call failed while the run stays alive
    (FR-030, FR-032). The category is a normalization hint; the default is
    an execution failure.
    """

    model_config = ConfigDict(frozen=True)

    message: str
    category: ErrorCategory = ErrorCategory.EXECUTION


AdapterOutput = TextBlock | ImageBlock | ErrorOutput


@runtime_checkable
class ToolAdapter(Protocol):
    def describe(self) -> Sequence[ToolDescriptor]: ...

    def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]: ...

    async def shutdown(self) -> None: ...
