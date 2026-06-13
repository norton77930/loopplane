"""External schema translation with a safe permissive fallback (FR-044)."""

from __future__ import annotations

PERMISSIVE_FALLBACK: dict[str, object] = {"type": "object"}


def translate_schema(raw: object) -> tuple[dict[str, object], bool]:
    """Translate an external input schema into the runtime's validation
    model. Returns (schema, fell_back): untranslatable constructs degrade to
    the permissive fallback rather than failing the tool.
    """
    if isinstance(raw, dict) and raw.get("type", "object") == "object":
        return dict(raw), False
    return dict(PERMISSIVE_FALLBACK), True
