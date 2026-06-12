"""The minimal Dispatcher: drives the session round-trip over abstract
send/receive channels — `submit-input` and `cancel` handling (FR-011,
FR-003).

The outbound side is the Controller's event sink; the inbound side is any
async iterable of consumer requests, so the same driver serves any future
host without modification. Approval decisions and question answers join the
inbound vocabulary in a later phase.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Sequence

import anyio
from pydantic import BaseModel, ConfigDict

from loopplane.controller.controller import RuntimeController
from loopplane.model.content import ContentBlock


class SubmitInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocks: tuple[ContentBlock, ...]


class Cancel(BaseModel):
    model_config = ConfigDict(frozen=True)


ConsumerRequest = SubmitInput | Cancel


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
        """Drive the round-trip until the inbound channel closes; cancel any
        in-flight run on close and never hang (FR-013 minimal form).
        """
        async with anyio.create_task_group() as task_group:
            try:
                async for request in self._inbound:
                    if isinstance(request, SubmitInput):
                        if self._driving:
                            await self._controller.emit_diagnostic(
                                self._session_id,
                                "warning",
                                "dispatcher",
                                "input rejected: a turn is already active",
                            )
                            continue
                        self._driving = True
                        task_group.start_soon(self._drive_one, list(request.blocks))
                    else:
                        self._controller.cancel(self._session_id)
            finally:
                if self._driving:
                    self._controller.cancel(self._session_id)

    async def _drive_one(self, blocks: Sequence[ContentBlock]) -> None:
        try:
            await self._controller.drive(self._session_id, blocks)
        finally:
            self._driving = False
