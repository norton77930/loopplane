"""The validation stage: JSON Schema with undeclared-property rejection
(FR-022; research R3). Runs before any execution.
"""

from __future__ import annotations

import jsonschema


def _declared_properties(schema: dict[str, object]) -> set[str] | None:
    """Collect declared property names from a schema, descending into
    ``allOf``/``anyOf``/``oneOf`` so composed object schemas are covered too.

    Returns ``None`` when no branch declares any properties — the schema's
    shape cannot be enumerated, so undeclared parameters cannot be judged.
    """
    names: set[str] = set()
    found = False
    properties = schema.get("properties")
    if isinstance(properties, dict):
        names |= set(properties)
        found = True
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            child = _declared_properties(branch)
            if child is not None:
                names |= child
                found = True
    return names if found else None


def validate_input(
    schema: dict[str, object], call_input: dict[str, object]
) -> str | None:
    """Return a problem description, or None when the input is valid.

    Undeclared parameters are rejected even when the schema itself does not
    forbid additional properties (FR-022 is unconditional), including object
    schemas whose properties are nested under JSON Schema composition.
    """
    try:
        jsonschema.validate(call_input, schema)
    except jsonschema.ValidationError as exc:
        return f"input does not match the declared schema: {exc.message}"
    except jsonschema.SchemaError as exc:
        return f"the declared schema is invalid: {exc.message}"
    declared = _declared_properties(schema)
    if declared is not None:
        undeclared = sorted(set(call_input) - declared)
        if undeclared:
            return "undeclared parameters: " + ", ".join(undeclared)
    return None
