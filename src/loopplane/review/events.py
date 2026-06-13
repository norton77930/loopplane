"""The Review Event vocabulary (contracts/gate-boundary.md; FR-050–FR-052).

A review-level lifecycle stream, distinct from Loop Events and Runtime Events.
Versioned and additive; consumers tolerate unknown future types.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

REVIEW_SCHEMA_VERSION: Final[str] = "1.0"

ReviewEventType = Literal[
    "review_requested",
    "review_question_asked",
    "review_question_answered",
    "review_decided",
    "review_resolved_from_memory",
]

REVIEW_EVENT_TYPES: Final[tuple[ReviewEventType, ...]] = (
    "review_requested",
    "review_question_asked",
    "review_question_answered",
    "review_decided",
    "review_resolved_from_memory",
)


@dataclass(frozen=True)
class ReviewEvent:
    """One review-level lifecycle record (FR-050)."""

    type: ReviewEventType
    sequence: int
    loop_id: str
    iteration_index: int | None = None
    session_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = REVIEW_SCHEMA_VERSION


ReviewEventSink = Callable[[ReviewEvent], Awaitable[None]]
