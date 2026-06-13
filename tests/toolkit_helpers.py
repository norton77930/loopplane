"""Deterministic, public-safe test helpers for the toolkit layer (008).

Scripted tool sources (``ToolAdapter`` doubles) and a recording registrar. The
scripted adapter's ``invoke`` raises immediately so any accidental invocation by
the toolkit layer fails a test (the layer must read ``describe()`` only).
"""

from __future__ import annotations

from collections.abc import Sequence

from loopplane.model import ToolDescriptor


def tool_descriptor(
    name: str,
    *,
    source: str = "internal",
    description: str = "",
    read_only: bool = False,
    concurrency_safe: bool = False,
    input_schema: dict[str, object] | None = None,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema if input_schema is not None else {"type": "object"},
        concurrency_safe=concurrency_safe,
        read_only=read_only,
        source=source,
    )


class ScriptedToolAdapter:
    """A ``ToolAdapter`` double: ``describe()`` returns the seeded descriptors (or
    raises); ``invoke`` raises immediately to catch accidental invocation."""

    def __init__(
        self, descriptors: Sequence[ToolDescriptor] = (), *, raising: bool = False
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._raising = raising

    def describe(self) -> Sequence[ToolDescriptor]:
        if self._raising:
            raise RuntimeError("describe boom")
        return self._descriptors

    def invoke(
        self, name: str, call_input: dict[str, object], context: object
    ) -> object:
        raise AssertionError("invoke must not be called by the toolkit layer")

    async def shutdown(self) -> None:
        return None


class RecordingRegistrar:
    """An ``AdapterRegistrar`` double recording each ``register_adapter`` call."""

    def __init__(self) -> None:
        self.registered: list[object] = []

    def register_adapter(self, adapter: object) -> None:
        self.registered.append(adapter)
