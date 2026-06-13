"""Output-size management: oversized results are reduced for the model
(FR-026). Artifact handoff activates with durable storage
(contracts/artifacts.md); until then reduction is purely bounded truncation.
"""

from __future__ import annotations

from loopplane.model.content import OutputBlock, TextBlock


def _block_size(block: OutputBlock) -> int:
    if isinstance(block, TextBlock):
        return len(block.text.encode("utf-8"))
    return len(block.media.encode("utf-8"))


def measure_outputs(outputs: list[OutputBlock]) -> int:
    return sum(_block_size(block) for block in outputs)


def reduce_outputs(outputs: list[OutputBlock], limit_bytes: int) -> list[OutputBlock]:
    total = measure_outputs(outputs)
    if total <= limit_bytes:
        return outputs

    reduced: list[OutputBlock] = []
    consumed = 0
    for block in outputs:
        size = _block_size(block)
        if isinstance(block, TextBlock):
            room = limit_bytes - consumed
            if size <= room:
                reduced.append(block)
                consumed += size
                continue
            if room > 0:
                kept = block.text.encode("utf-8")[:room].decode(
                    "utf-8", errors="ignore"
                )
                reduced.append(TextBlock(text=kept))
            break
        if consumed + size > limit_bytes:
            break
        reduced.append(block)
        consumed += size

    reduced.append(
        TextBlock(
            text=(
                f"[output truncated: {total} bytes exceeded "
                f"the {limit_bytes}-byte result limit]"
            )
        )
    )
    return reduced
