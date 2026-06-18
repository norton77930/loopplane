"""The ``read_upload`` Tool Gateway tool (unit 028).

The agent reads an uploaded file **on demand** by reference — read-only, transient
input, never embedded into the content model (Constitution V permits new tools in the
gateway; the content/prompt contract is unchanged, so no ADR). The tool is decoupled
from storage: it takes a ``read(reference) -> bytes | None`` callable (e.g.
``UploadStore.read``), so it carries no web dependency and is wired into a host's
``config.tools`` by the operator.
"""

from __future__ import annotations

from collections.abc import Callable

from loopplane.context import RunContext
from loopplane.host.config import ToolSpec
from loopplane.model import OutputBlock, TextBlock, ToolDescriptor

_READ_TEXT_LIMIT = 50_000

READ_UPLOAD_DESCRIPTOR = ToolDescriptor(
    name="read_upload",
    description="Read the text content of an uploaded file by its reference.",
    input_schema={
        "type": "object",
        "properties": {"reference": {"type": "string"}},
        "required": ["reference"],
        "additionalProperties": False,
    },
    read_only=True,
)


def make_read_upload_tool(read: Callable[[str], bytes | None]) -> ToolSpec:
    """A gateway tool that reads an uploaded file by reference (read-only)."""

    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        reference = str(call_input.get("reference", ""))
        data = read(reference)
        if data is None:
            return [TextBlock(text="upload not found")]
        text = data.decode("utf-8", errors="replace")
        if len(text) > _READ_TEXT_LIMIT:
            text = text[:_READ_TEXT_LIMIT] + "\n... (truncated)"
        return [TextBlock(text=text)]

    return ToolSpec(descriptor=READ_UPLOAD_DESCRIPTOR, handler=handler)
