"""Map the loop's normalized shapes to and from the OpenAI chat-completions API (020).

Provider chunks are consumed by duck-typing (``getattr``/``isinstance``), so the mapping
needs no SDK types and is exercised with plain stand-in chunks. OpenAI separates tool
calls (assistant ``tool_calls``) and tool results (``role: tool`` messages), and streams
tool-call arguments as fragments accumulated by index.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from loopplane.model.boundary import (
    Message,
    ModelIncrement,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
    ToolDescriptor,
    TurnEnd,
)
from loopplane.model.content import (
    DocumentBlock,
    ImageBlock,
    SummaryMarkerBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


class UnsupportedContentError(ValueError):
    """Raised when chat-completions mapping cannot represent a content block."""


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _digest_text(block: SummaryMarkerBlock) -> str:
    digest = block.digest
    head = f"[summary of {digest.turn_count} earlier turns]"
    if digest.tool_names:
        head += " tools: " + ", ".join(digest.tool_names)
    return "\n".join([head, *digest.excerpts])


def _parse_args(raw: str) -> dict[str, object]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_tools(tools: Iterable[ToolDescriptor]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool in tools
    ]


def build_messages(context: Iterable[Message]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for message in context:
        _reject_unsupported_documents(message.blocks)
        results = [b for b in message.blocks if isinstance(b, ToolResultBlock)]
        if results:
            for result in results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.call_id,
                        "content": _tool_result_text(result),
                    }
                )
            continue
        messages.append(_assistant_or_user(message))
    return messages


def _reject_unsupported_documents(blocks: Iterable[Any]) -> None:
    if any(isinstance(block, DocumentBlock) for block in blocks):
        raise UnsupportedContentError(
            "document input is not supported by this provider"
        )


def _assistant_or_user(message: Message) -> dict[str, Any]:
    text_parts: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    has_image = False
    for block in message.blocks:
        if isinstance(block, TextBlock):
            text_parts.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageBlock):
            has_image = True
            text_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{block.format};base64,{block.media}"},
                }
            )
        elif isinstance(block, ToolCallBlock):
            tool_calls.append(
                {
                    "id": block.call_id,
                    "type": "function",
                    "function": {
                        "name": block.tool_name,
                        "arguments": json.dumps(block.input),
                    },
                }
            )
        elif isinstance(block, SummaryMarkerBlock):
            text_parts.append({"type": "text", "text": _digest_text(block)})

    out: dict[str, Any] = {"role": message.role}
    if has_image:
        out["content"] = text_parts
    else:
        text = "".join(
            str(part["text"]) for part in text_parts if part["type"] == "text"
        )
        out["content"] = text if text else (None if tool_calls else "")
    if tool_calls:
        out["tool_calls"] = tool_calls
    return out


def _tool_result_text(result: ToolResultBlock) -> str:
    parts = [output.text for output in result.outputs if isinstance(output, TextBlock)]
    if not parts and result.error is not None:
        parts = [result.error.reason]
    return "".join(parts)


class OpenAIStreamDecoder:
    """Turns the OpenAI chat-completions chunk stream into normalized increments.

    Text deltas yield increments immediately; tool-call fragments accumulate by index
    and are emitted, with the single ``TurnEnd``, by ``finish`` once the stream ends (so
    the trailing usage-only chunk is included).
    """

    def __init__(self) -> None:
        self._tools: dict[int, dict[str, str]] = {}
        self._order: list[int] = []
        self._stop_reason = "stop"
        self._input = 0
        self._output = 0
        self._cached = 0
        self._reasoning = 0

    def feed(self, chunk: object) -> list[ModelIncrement]:
        self._apply_usage(getattr(chunk, "usage", None))
        out: list[ModelIncrement] = []
        choices = getattr(chunk, "choices", None) or []
        for choice in choices:
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                out.append(TextIncrement(text=content))
            self._accumulate(getattr(delta, "tool_calls", None))
            finish = getattr(choice, "finish_reason", None)
            if isinstance(finish, str):
                self._stop_reason = finish
        return out

    def finish(self) -> list[ModelIncrement]:
        out: list[ModelIncrement] = []
        for index in self._order:
            tool = self._tools[index]
            out.append(
                ToolCallRequest(
                    call_id=tool["id"] or f"call_{index}",
                    tool_name=tool["name"],
                    input=_parse_args(tool["args"]),
                )
            )
        out.append(
            TurnEnd(
                stop_reason=self._stop_reason,
                usage=TokenUsage(
                    input_tokens=self._input,
                    output_tokens=self._output,
                    cached_tokens=self._cached,
                    reasoning_tokens=self._reasoning,
                ),
            )
        )
        return out

    def _accumulate(self, tool_calls: Any) -> None:
        if not tool_calls:
            return
        for call in tool_calls:
            index = _int(getattr(call, "index", 0))
            slot = self._tools.get(index)
            if slot is None:
                slot = {"id": "", "name": "", "args": ""}
                self._tools[index] = slot
                self._order.append(index)
            identifier = getattr(call, "id", None)
            if isinstance(identifier, str) and identifier:
                slot["id"] = identifier
            function = getattr(call, "function", None)
            name = getattr(function, "name", None)
            if isinstance(name, str) and name:
                slot["name"] = name
            arguments = getattr(function, "arguments", None)
            if isinstance(arguments, str):
                slot["args"] += arguments

    def _apply_usage(self, usage: object) -> None:
        if usage is None:
            return
        self._input = _int(getattr(usage, "prompt_tokens", 0)) or self._input
        self._output = _int(getattr(usage, "completion_tokens", 0)) or self._output
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        cached = _int(getattr(prompt_details, "cached_tokens", 0))
        if cached:
            self._cached = cached
        completion_details = getattr(usage, "completion_tokens_details", None)
        reasoning = _int(getattr(completion_details, "reasoning_tokens", 0))
        if reasoning:
            self._reasoning = reasoning
