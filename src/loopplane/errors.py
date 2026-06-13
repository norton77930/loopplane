"""The Normalized Error shape (data-model.md; FR-025).

The single failure shape that crosses the Tool Gateway boundary. The reason
text is safe to show to the model; raw adapter internals never leak through.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ErrorCategory(StrEnum):
    UNKNOWN_TOOL = "unknown-tool"
    VALIDATION = "validation"
    POLICY_DENIAL = "policy-denial"
    TIMEOUT = "timeout"
    EXECUTION = "execution"
    ADAPTER_FAULT = "adapter-fault"


class NormalizedError(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ErrorCategory
    reason: str
