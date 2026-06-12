"""Lossless event serialization (FR-064, NFR-006) with unknown-type and
corrupt-input tolerance (FR-063).
"""

from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from loopplane.events.envelope import RUNTIME_EVENT_TYPES, RuntimeEvent

_adapter: TypeAdapter[RuntimeEvent] = TypeAdapter(RuntimeEvent)


def serialize_event(event: RuntimeEvent) -> str:
    """Serialize one event to a self-describing JSON document."""
    return _adapter.dump_json(event).decode("utf-8")


def deserialize_event(data: str | bytes) -> RuntimeEvent | None:
    """Deserialize one event; unknown types and corrupt input yield None."""
    try:
        document = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("type") not in RUNTIME_EVENT_TYPES:
        return None
    try:
        return _adapter.validate_python(document)
    except ValidationError:
        return None
