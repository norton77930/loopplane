"""Mapping between the loop's normalized shapes and the Anthropic messages API (020).

Provider events are consumed by duck-typing (``getattr``/``isinstance``), so the mapping
needs no SDK types and is exercised with plain stand-in events.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from loopplane.model.boundary import (
    Message,
    ModelIncrement,
    ReasoningIncrement,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
    ToolDescriptor,
    TurnEnd,
)
from loopplane.model.content import (
    ContentBlock,
    ImageBlock,
    SummaryMarkerBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _digest_text(block: SummaryMarkerBlock) -> str:
    digest = block.digest
    head = f"[summary of {digest.turn_count} earlier turns]"
    if digest.tool_names:
        head += " tools: " + ", ".join(digest.tool_names)
    return "\n".join([head, *digest.excerpts])


def build_tools(tools: Iterable[ToolDescriptor]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]


def build_messages(context: Iterable[Message]) -> list[dict[str, Any]]:
    return [
        {"role": message.role, "content": _content(message.blocks)}
        for message in context
    ]


def _content(blocks: Iterable[ContentBlock]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextBlock):
            out.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageBlock):
            out.append(_image(block.media, block.format))
        elif isinstance(block, ToolCallBlock):
            out.append(
                {
                    "type": "tool_use",
                    "id": block.call_id,
                    "name": block.tool_name,
                    "input": block.input,
                }
            )
        elif isinstance(block, ToolResultBlock):
            out.append(_tool_result(block))
        elif isinstance(block, SummaryMarkerBlock):
            out.append({"type": "text", "text": _digest_text(block)})
    return out


def _image(media: str, fmt: str) -> dict[str, Any]:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": fmt, "data": media},
    }


def _tool_result(block: ToolResultBlock) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for output in block.outputs:
        if isinstance(output, TextBlock):
            content.append({"type": "text", "text": output.text})
        elif isinstance(output, ImageBlock):
            content.append(_image(output.media, output.format))
    if not content and block.error is not None:
        content.append({"type": "text", "text": block.error.reason})
    if not content:
        content.append({"type": "text", "text": ""})
    result: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": block.call_id,
        "content": content,
    }
    if block.outcome == "failure":
        result["is_error"] = True
    return result


class AnthropicStreamDecoder:
    """Turns the Anthropic raw message stream into normalized increments.

    Stateful across one turn: text/reasoning deltas yield increments immediately, a
    completed ``tool_use`` block yields a :class:`ToolCallRequest`, and ``message_stop``
    yields the single :class:`TurnEnd`.
    """

    def __init__(self) -> None:
        self._tools: dict[int, dict[str, str]] = {}
        self._stop_reason = "end_turn"
        self._input = 0
        self._output = 0
        self._cached = 0
        self._ended = False

    @property
    def ended(self) -> bool:
        return self._ended

    def feed(self, event: object) -> list[ModelIncrement]:
        kind = getattr(event, "type", None)
        if kind == "message_start":
            self._apply_input_usage(event)
            return []
        if kind == "content_block_start":
            self._open_block(event)
            return []
        if kind == "content_block_delta":
            return self._delta(event)
        if kind == "content_block_stop":
            return self._close_block(event)
        if kind == "message_delta":
            self._apply_message_delta(event)
            return []
        if kind == "message_stop":
            self._ended = True
            return [self.turn_end()]
        return []

    def turn_end(self) -> TurnEnd:
        return TurnEnd(
            stop_reason=self._stop_reason,
            usage=TokenUsage(
                input_tokens=self._input,
                output_tokens=self._output,
                cached_tokens=self._cached,
            ),
        )

    def _apply_input_usage(self, event: object) -> None:
        usage = getattr(getattr(event, "message", None), "usage", None)
        self._input = _int(getattr(usage, "input_tokens", 0))
        self._cached = _int(getattr(usage, "cache_read_input_tokens", 0))

    def _open_block(self, event: object) -> None:
        block = getattr(event, "content_block", None)
        if getattr(block, "type", None) == "tool_use":
            index = _int(getattr(event, "index", 0))
            self._tools[index] = {
                "id": str(getattr(block, "id", "")),
                "name": str(getattr(block, "name", "")),
                "json": "",
            }

    def _delta(self, event: object) -> list[ModelIncrement]:
        delta = getattr(event, "delta", None)
        kind = getattr(delta, "type", None)
        if kind == "text_delta":
            text = getattr(delta, "text", None)
            if isinstance(text, str) and text:
                return [TextIncrement(text=text)]
        elif kind == "thinking_delta":
            thinking = getattr(delta, "thinking", None)
            if isinstance(thinking, str) and thinking:
                return [ReasoningIncrement(text=thinking)]
        elif kind == "input_json_delta":
            index = _int(getattr(event, "index", 0))
            partial = getattr(delta, "partial_json", None)
            if index in self._tools and isinstance(partial, str):
                self._tools[index]["json"] += partial
        return []

    def _close_block(self, event: object) -> list[ModelIncrement]:
        index = _int(getattr(event, "index", 0))
        tool = self._tools.pop(index, None)
        if tool is None:
            return []
        raw = tool["json"]
        parsed: dict[str, object] = {}
        if raw:
            try:
                loaded = json.loads(raw)
            except (ValueError, TypeError):
                loaded = None
            if isinstance(loaded, dict):
                parsed = loaded
        return [
            ToolCallRequest(call_id=tool["id"], tool_name=tool["name"], input=parsed)
        ]

    def _apply_message_delta(self, event: object) -> None:
        stop = getattr(getattr(event, "delta", None), "stop_reason", None)
        if isinstance(stop, str):
            self._stop_reason = stop
        usage = getattr(event, "usage", None)
        output = _int(getattr(usage, "output_tokens", 0))
        if output:
            self._output = output
