"""The prompt assembler (FR-073; plan D2): assembly-time augmentation with
pristine durable history. Augmentations — memory selections, skill
advertisements — exist only in the assembled model context; the history
itself is never altered by assembly.

The assembler also owns proactive compaction sizing (FR-008) and
post-compaction re-establishment of needed augmentations (FR-053).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from loopplane.loop.compaction import DEFAULT_KEEP_LAST, compact_history
from loopplane.loop.history import SessionHistory
from loopplane.model.boundary import Message, ModelRequest, ToolDescriptor
from loopplane.model.content import ContentBlock, TextBlock, ToolResultBlock

_NON_TEXT_BLOCK_COST = 50


class AugmentationProvider(Protocol):
    """An assembly-time augmentation source (memory, skill advertisement)."""

    def augment_for(self, prompt: str) -> str | None: ...

    def re_establish(self) -> str | None: ...


class PromptAssembler:
    def __init__(
        self,
        *,
        providers: Sequence[AugmentationProvider] = (),
        replacement_previews: Callable[[], Mapping[str, str]] | None = None,
        keep_last: int = DEFAULT_KEEP_LAST,
        chars_per_token: int = 4,
    ) -> None:
        self._providers = list(providers)
        self._replacement_previews = replacement_previews
        self.keep_last = keep_last
        self._chars_per_token = chars_per_token
        self._needs_reestablish = False

    def mark_compacted(self) -> None:
        """Called after compaction so the next assembly re-establishes the
        content the model still needs (FR-053).
        """
        self._needs_reestablish = True

    def assemble(
        self,
        *,
        history: SessionHistory,
        tools: Sequence[ToolDescriptor],
        capacity: int,
        prompt: str,
    ) -> ModelRequest:
        fresh = [
            text
            for provider in self._providers
            if (text := provider.augment_for(prompt))
        ]
        re_established: list[str] = []
        if self._needs_reestablish:
            self._needs_reestablish = False
            re_established = self._collect_reestablished()
        request = self._compose(history, tools, re_established + fresh)

        # Proactive compaction: when the assembled context approaches the
        # model's capacity, compact and rebuild once (FR-008).
        if self._estimate_tokens(request) > capacity and compact_history(
            history, keep_last=self.keep_last
        ):
            re_established = self._collect_reestablished()
            request = self._compose(history, tools, re_established + fresh)
        return request

    def _collect_reestablished(self) -> list[str]:
        return [
            text for provider in self._providers if (text := provider.re_establish())
        ]

    def _compose(
        self,
        history: SessionHistory,
        tools: Sequence[ToolDescriptor],
        sections: Sequence[str],
    ) -> ModelRequest:
        messages: list[Message] = []
        if sections:
            messages.append(
                Message(role="user", blocks=[TextBlock(text="\n\n".join(sections))])
            )
        previews: Mapping[str, str] = (
            self._replacement_previews() if self._replacement_previews else {}
        )
        for entry in history.snapshot():
            blocks = [
                self._apply_replacement(block, previews) for block in entry.blocks
            ]
            messages.append(Message(role=entry.role, blocks=blocks))
        return ModelRequest(context=messages, tools=list(tools))

    @staticmethod
    def _apply_replacement(
        block: ContentBlock, previews: Mapping[str, str]
    ) -> ContentBlock:
        if isinstance(block, ToolResultBlock) and block.call_id in previews:
            return ToolResultBlock(
                call_id=block.call_id,
                outcome=block.outcome,
                outputs=[TextBlock(text=previews[block.call_id])],
                error=block.error,
                artifact_reference=block.artifact_reference,
            )
        return block

    def _estimate_tokens(self, request: ModelRequest) -> int:
        chars = 0
        for message in request.context:
            for block in message.blocks:
                if isinstance(block, TextBlock):
                    chars += len(block.text)
                else:
                    chars += _NON_TEXT_BLOCK_COST
        return chars // self._chars_per_token
