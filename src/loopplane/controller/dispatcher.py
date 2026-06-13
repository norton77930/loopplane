"""The Dispatcher: drives the session round-trip over abstract send/receive
channels (FR-011) — submit-input, cancel, approval decisions, and question
answers (FR-003, FR-012).

The outbound side is the Controller's event sink; the inbound side is any
async iterable of consumer requests, so the same driver serves any future
host without modification.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Sequence
from typing import Literal

import anyio
from pydantic import BaseModel, ConfigDict

from loopplane.controller.controller import RuntimeController
from loopplane.events.emitter import EventSink
from loopplane.events.envelope import RuntimeEvent
from loopplane.model.content import ContentBlock

_INCREMENT_TYPES = ("assistant-output-increment", "assistant-reasoning-increment")


class BatchingSink:
    """Optional outbound batching (FR-015): rapid increments MAY buffer for
    delivery efficiency, but any non-incremental event flushes buffered
    increments first — nothing is ever reordered.
    """

    def __init__(self, inner: EventSink, *, max_buffer: int = 16) -> None:
        self._inner = inner
        self._buffer: list[RuntimeEvent] = []
        self._max_buffer = max_buffer

    async def __call__(self, event: RuntimeEvent) -> None:
        if event.type in _INCREMENT_TYPES:
            self._buffer.append(event)
            if len(self._buffer) >= self._max_buffer:
                await self.flush()
            return
        await self.flush()
        await self._inner(event)

    async def flush(self) -> None:
        buffered, self._buffer = self._buffer, []
        for event in buffered:
            await self._inner(event)


class SubmitInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocks: tuple[ContentBlock, ...]


class Cancel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    decision: Literal["allow", "deny"]
    scope: Literal["once", "session"] = "once"
    reason: str | None = None


class QuestionAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    answers: tuple[str, ...]


ConsumerRequest = SubmitInput | Cancel | ApprovalDecision | QuestionAnswer


class Dispatcher:
    def __init__(
        self,
        *,
        controller: RuntimeController,
        session_id: str,
        inbound: AsyncIterable[ConsumerRequest],
    ) -> None:
        self._controller = controller
        self._session_id = session_id
        self._inbound = inbound
        self._driving = False

    async def run(self) -> None:
        """Drive the round-trip until the inbound channel closes. On close
        (FR-013): cancel in-flight work, deny every pending approval, cancel
        pending questions, and never hang.
        """
        self._controller.attach_reviewer(self._session_id)
        async with anyio.create_task_group() as task_group:
            try:
                async for request in self._inbound:
                    await self._handle(request, task_group)
            finally:
                if self._driving:
                    self._controller.cancel(self._session_id)
                self._controller.on_reviewer_disconnect(self._session_id)

    async def _handle(
        self, request: ConsumerRequest, task_group: anyio.abc.TaskGroup
    ) -> None:
        if isinstance(request, SubmitInput):
            if self._driving:
                await self._controller.emit_diagnostic(
                    self._session_id,
                    "warning",
                    "dispatcher",
                    "input rejected: a turn is already active",
                )
                return
            self._driving = True
            task_group.start_soon(self._drive_one, list(request.blocks))
        elif isinstance(request, Cancel):
            self._controller.cancel(self._session_id)
        elif isinstance(request, ApprovalDecision):
            applied = self._controller.resolve_approval(
                self._session_id,
                request.request_id,
                decision=request.decision,
                scope=request.scope,
                reason=request.reason,
            )
            if not applied:
                await self._controller.emit_diagnostic(
                    self._session_id,
                    "warning",
                    "dispatcher",
                    f"approval decision ignored: unknown or already-resolved "
                    f"request {request.request_id}",
                )
        else:
            applied = self._controller.answer_question(
                self._session_id, request.request_id, list(request.answers)
            )
            if not applied:
                await self._controller.emit_diagnostic(
                    self._session_id,
                    "warning",
                    "dispatcher",
                    f"question answer ignored: unknown or already-resolved "
                    f"request {request.request_id}",
                )

    async def _drive_one(self, blocks: Sequence[ContentBlock]) -> None:
        try:
            await self._controller.drive(self._session_id, blocks)
        finally:
            self._driving = False
