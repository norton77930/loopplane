"""The validation stage: JSON Schema with undeclared-property rejection
(FR-022; research R3). Runs before any execution.
"""

from __future__ import annotations

import jsonschema


def validate_input(
    schema: dict[str, object], call_input: dict[str, object]
) -> str | None:
    """Return a problem description, or None when the input is valid.

    Undeclared parameters are rejected even when the schema itself does not
    forbid additional properties (FR-022 is unconditional).
    """
    try:
        jsonschema.validate(call_input, schema)
    except jsonschema.ValidationError as exc:
        return f"input does not match the declared schema: {exc.message}"
    except jsonschema.SchemaError as exc:
        return f"the declared schema is invalid: {exc.message}"
    properties = schema.get("properties")
    if isinstance(properties, dict):
        undeclared = sorted(set(call_input) - set(properties))
        if undeclared:
            return "undeclared parameters: " + ", ".join(undeclared)
    return None
