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


def estimate_request_tokens(request: ModelRequest, *, chars_per_token: int = 4) -> int:
    """Estimate request tokens with the assembler's local sizing heuristic."""
    chars = 0
    for message in request.context:
        for block in message.blocks:
            if isinstance(block, TextBlock):
                chars += len(block.text)
            else:
                chars += _NON_TEXT_BLOCK_COST
    return chars // chars_per_token


class PromptAssembler:
    def __init__(
        self,
        *,
        providers: Sequence[AugmentationProvider] = (),
        replacement_previews: Callable[[], Mapping[str, str]] | None = None,
        keep_last: int = DEFAULT_KEEP_LAST,
        chars_per_token: int = 4,
        compact_threshold: float | None = None,
    ) -> None:
        self._providers = list(providers)
        self._replacement_previews = replacement_previews
        self.keep_last = keep_last
        self._chars_per_token = chars_per_token
        # Proactive-compaction threshold (spec 041): None reuses the model's full
        # capacity (the existing behavior — byte-identical); a fraction f in (0, 1]
        # compacts proactively at f * capacity, a safety margin before the limit.
        self._compact_threshold = compact_threshold
        self._needs_reestablish = False
        # One-shot signal (spec 042): set when the proactive path compacts inside
        # `assemble`, read-and-cleared by the loop so it can run the optional
        # compaction summarizer over the just-dropped span.
        self._just_compacted = False

    def mark_compacted(self) -> None:
        """Called after compaction so the next assembly re-establishes the
        content the model still needs (FR-053).
        """
        self._needs_reestablish = True

    def take_compacted(self) -> bool:
        """Read-and-clear the one-shot proactive-compaction signal (spec 042):
        ``True`` exactly once after the proactive path ran ``compact_history`` in
        ``assemble``, so the loop knows to run the summarizer overlay. ``False``
        when no proactive compaction occurred.
        """
        compacted = self._just_compacted
        self._just_compacted = False
        return compacted

    def assemble(
        self,
        *,
        history: SessionHistory,
        tools: Sequence[ToolDescriptor],
        capacity: int,
        prompt: str,
        output_schema: dict[str, object] | None = None,
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
        request = self._compose(history, tools, re_established + fresh, output_schema)

        # Proactive compaction: when the assembled context approaches the
        # model's (effective) capacity, compact and rebuild once (FR-008). The
        # effective capacity is the full capacity by default, or a configured
        # fraction of it (spec 041) so compaction runs earlier, on a safety margin.
        if self._estimate_tokens(request) > self._effective_capacity(
            capacity
        ) and compact_history(history, keep_last=self.keep_last):
            # Signal the loop so it can run the optional compaction summarizer
            # over the just-dropped span (spec 042); the mechanical marker is
            # already in history and stands if no summarizer is configured.
            self._just_compacted = True
            re_established = self._collect_reestablished()
            request = self._compose(
                history, tools, re_established + fresh, output_schema
            )
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
        output_schema: dict[str, object] | None = None,
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
        return ModelRequest(
            context=messages, tools=list(tools), output_schema=output_schema
        )

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

    def _effective_capacity(self, capacity: int) -> int:
        """The capacity the proactive pre-send check compares against (spec 041):
        the model's full capacity when no threshold is set (the existing
        behavior), else a configured fraction of it so compaction runs earlier.
        """
        if self._compact_threshold is None:
            return capacity
        return int(capacity * self._compact_threshold)

    def _estimate_tokens(self, request: ModelRequest) -> int:
        return estimate_request_tokens(request, chars_per_token=self._chars_per_token)
