"""Gating decisions a hook may return at the two gating points (FR-006, FR-007;
contracts/hooks.md).

The callback returns one of these; the Gateway (for tool calls) or the Loop (for
prompts) applies the effect — a callback never executes the effect itself
(Constitution V/VI). ``reason`` and ``text`` MUST be public-safe (FR-015).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- before_tool_use ---


@dataclass(frozen=True)
class ToolGateAllow:
    """No opinion: let the call proceed unchanged."""


@dataclass(frozen=True)
class ToolGateDeny:
    """Block the call; ``reason`` is surfaced as a normalized policy denial."""

    reason: str


@dataclass(frozen=True)
class ToolGateModify:
    """Replace the call's inputs (re-validated before execution)."""

    input: dict[str, object] = field(default_factory=dict)


ToolGateDecision = ToolGateAllow | ToolGateDeny | ToolGateModify


# --- user_prompt_submit ---


@dataclass(frozen=True)
class PromptAllow:
    """No opinion: let the prompt reach the model unchanged."""


@dataclass(frozen=True)
class PromptBlock:
    """Block the prompt; the model is not invoked for it."""

    reason: str


@dataclass(frozen=True)
class PromptAnnotate:
    """Augment the prompt the model receives with extra public-safe context."""

    text: str


PromptDecision = PromptAllow | PromptBlock | PromptAnnotate
