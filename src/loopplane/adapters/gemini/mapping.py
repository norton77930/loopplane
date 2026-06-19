"""Map the loop's normalized shapes to and from the native Google GenAI API (037).

Gemini's wire format is its own: a request is ``contents`` (a list of role + ``parts``)
plus ``tools`` (``function_declarations``); a streamed response is a sequence of chunks
whose ``candidates[0].content.parts`` carry text / thought / ``function_call`` /
``inline_data``, with a trailing ``usage_metadata``. The mapping emits **plain dicts**
(the SDK accepts dict-shaped ``contents``/``tools``) and consumes the response stream by
**duck-typing** (``getattr``/``isinstance``), so it needs no SDK types and is exercised
with plain stand-in chunks (mirroring the unit-020 adapters).

``thought_signature`` (037, conservative path): Gemini 3 hard-requires a per-
``function_call`` signature echoed back on the next turn. The shared content model
(``ToolCallBlock``) has no field for it (ADR 0001 kept the content model unchanged), so
when re-mapping a prior tool call this attaches Google's **official** sentinel
``"skip_thought_signature_validator"`` to the ``function_call`` part to skip
validation — never smuggling it into the tool-input ``args`` the gateway validates.
Preserving the *real* signature would need a content-model field (a Constitution VI /
ADR matter) and is a documented deferred follow-up.
"""

from __future__ import annotations

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
    ImageBlock,
    SummaryMarkerBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)

# Google's official sentinel to skip thought_signature validation when a real
# per-function_call signature is not preserved (Gemini thought-signatures docs FAQ).
SKIP_THOUGHT_SIGNATURE = "skip_thought_signature_validator"


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _digest_text(block: SummaryMarkerBlock) -> str:
    digest = block.digest
    head = f"[summary of {digest.turn_count} earlier turns]"
    if digest.tool_names:
        head += " tools: " + ", ".join(digest.tool_names)
    return "\n".join([head, *digest.excerpts])


def build_tools(tools: Iterable[ToolDescriptor]) -> list[dict[str, Any]]:
    declarations = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        }
        for tool in tools
    ]
    if not declarations:
        return []
    return [{"function_declarations": declarations}]


def build_contents(context: Iterable[Message]) -> list[dict[str, Any]]:
    return [
        {
            "role": "model" if message.role == "assistant" else "user",
            "parts": _parts(message.blocks),
        }
        for message in context
    ]


def _parts(blocks: Iterable[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextBlock):
            out.append({"text": block.text})
        elif isinstance(block, ImageBlock):
            out.append(
                {"inline_data": {"mime_type": block.format, "data": block.media}}
            )
        elif isinstance(block, ToolCallBlock):
            out.append(
                {
                    "function_call": {
                        "name": block.tool_name,
                        "args": block.input,
                    },
                    # The official multi-turn bypass: a real per-call signature has
                    # nowhere to live in the shared content model (ADR 0001), so skip
                    # validation rather than invent a value or change the model.
                    "thought_signature": SKIP_THOUGHT_SIGNATURE,
                }
            )
        elif isinstance(block, ToolResultBlock):
            out.append(
                {
                    "function_response": {
                        "name": block.call_id,
                        "response": _tool_result_response(block),
                    }
                }
            )
        elif isinstance(block, SummaryMarkerBlock):
            out.append({"text": _digest_text(block)})
    return out


def _tool_result_response(block: ToolResultBlock) -> dict[str, Any]:
    parts = [output.text for output in block.outputs if isinstance(output, TextBlock)]
    if not parts and block.error is not None:
        parts = [block.error.reason]
    return {"output": "".join(parts)}


class GeminiStreamDecoder:
    """Turns the Gemini chunk stream into normalized increments.

    Stateful across one turn: text/thought parts yield increments immediately, a
    ``function_call`` part accumulates and is emitted (with the single :class:`TurnEnd`)
    by ``finish`` once the stream ends (so the trailing ``usage_metadata`` is included).
    Gemini ``function_call`` parts carry no id, so a stable ``call_<n>`` id is made up.
    """

    def __init__(self) -> None:
        self._calls: list[ToolCallRequest] = []
        self._stop_reason = "stop"
        self._input = 0
        self._output = 0
        self._cached = 0
        self._reasoning = 0

    def feed(self, chunk: object) -> list[ModelIncrement]:
        self._apply_usage(getattr(chunk, "usage_metadata", None))
        out: list[ModelIncrement] = []
        for candidate in getattr(chunk, "candidates", None) or []:
            finish = getattr(candidate, "finish_reason", None)
            if finish is not None:
                self._stop_reason = str(finish)
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                out.extend(self._part(part))
        return out

    def finish(self) -> list[ModelIncrement]:
        out: list[ModelIncrement] = list(self._calls)
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

    def _part(self, part: object) -> list[ModelIncrement]:
        call = getattr(part, "function_call", None)
        if call is not None:
            name = getattr(call, "name", None)
            args = getattr(call, "args", None)
            self._calls.append(
                ToolCallRequest(
                    call_id=f"call_{len(self._calls)}",
                    tool_name=str(name) if isinstance(name, str) else "",
                    input=dict(args) if isinstance(args, dict) else {},
                )
            )
            return []
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            if getattr(part, "thought", None) is True:
                return [ReasoningIncrement(text=text)]
            return [TextIncrement(text=text)]
        return []

    def _apply_usage(self, usage: object) -> None:
        if usage is None:
            return
        self._input = _int(getattr(usage, "prompt_token_count", 0)) or self._input
        self._output = _int(getattr(usage, "candidates_token_count", 0)) or self._output
        cached = _int(getattr(usage, "cached_content_token_count", 0))
        if cached:
            self._cached = cached
        reasoning = _int(getattr(usage, "thoughts_token_count", 0))
        if reasoning:
            self._reasoning = reasoning
