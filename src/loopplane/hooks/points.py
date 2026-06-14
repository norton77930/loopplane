"""Lifecycle points and their metadata-only payloads (spec FR-002, FR-015;
data-model.md).

Every payload is a frozen dataclass holding only public-safe metadata — never
raw tool output, raw exception text, secrets, or private absolute paths. The two
gating points (``before_tool_use``, ``user_prompt_submit``) carry the datum a
gating hook may decide on (``input`` / ``text``); the dispatcher applies a hook's
decision rather than letting a callback mutate the payload in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class LifecyclePoint(StrEnum):
    """The eleven moments at which the runtime invites hooks (FR-002)."""

    before_tool_use = "before_tool_use"
    after_tool_use = "after_tool_use"
    after_tool_failure = "after_tool_failure"
    user_prompt_submit = "user_prompt_submit"
    session_start = "session_start"
    session_end = "session_end"
    process_setup = "process_setup"
    subagent_start = "subagent_start"
    subagent_stop = "subagent_stop"
    file_changed = "file_changed"
    model_stop = "model_stop"


#: The points at which a hook may gate or modify (all others are observational).
GATING_POINTS: frozenset[LifecyclePoint] = frozenset(
    {LifecyclePoint.before_tool_use, LifecyclePoint.user_prompt_submit}
)


def is_gating(point: LifecyclePoint) -> bool:
    """Whether ``point`` accepts a gating decision (vs. observe-only)."""
    return point in GATING_POINTS


@dataclass(frozen=True)
class BeforeToolUsePayload:
    session_id: str
    call_id: str
    tool_name: str
    input: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AfterToolUsePayload:
    session_id: str
    call_id: str
    tool_name: str
    duration_seconds: float
    outcome: str = "success"


@dataclass(frozen=True)
class AfterToolFailurePayload:
    session_id: str
    call_id: str
    tool_name: str
    error_category: str
    reason: str


@dataclass(frozen=True)
class FileChangedPayload:
    session_id: str
    call_id: str
    tool_name: str
    path: str


@dataclass(frozen=True)
class UserPromptSubmitPayload:
    session_id: str
    text: str


@dataclass(frozen=True)
class SessionStartPayload:
    session_id: str
    label: str | None = None


@dataclass(frozen=True)
class SessionEndPayload:
    session_id: str
    state: str


@dataclass(frozen=True)
class ProcessSetupPayload:
    pass


@dataclass(frozen=True)
class SubagentStartPayload:
    session_id: str
    subagent: str
    agent_type: str


@dataclass(frozen=True)
class SubagentStopPayload:
    session_id: str
    subagent: str
    outcome: str


@dataclass(frozen=True)
class ModelStopPayload:
    session_id: str
    turns_taken: int
