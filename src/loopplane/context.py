"""The Run Context: per-run execution scope handed to tools and policies
(data-model.md; FR-003, FR-113).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import anyio


@dataclass
class RunContext:
    session_id: str
    working_scope: Path
    cancellation: anyio.Event = field(default_factory=anyio.Event)
    turn_budget: int | None = None
    session_approval_memory: dict[str, Literal["allow", "deny"]] = field(
        default_factory=dict
    )
    feature_toggles: dict[str, bool] = field(default_factory=dict)
