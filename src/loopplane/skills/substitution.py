"""Closed-list variable substitution (FR-054): only runtime-provided
variables from the closed list substitute; everything else passes through
literally.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

CLOSED_VARIABLES: Final[tuple[str, ...]] = ("session_id", "working_scope", "arguments")

_VARIABLE = re.compile(r"\$\{(\w+)\}")


def substitute(text: str, values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in CLOSED_VARIABLES and name in values:
            return values[name]
        return match.group(0)

    return _VARIABLE.sub(replace, text)
