"""Skill and execution-profile shapes (data-model.md; FR-050; research A1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ExecutionProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    autonomous_invocation: Literal["allowed", "forbidden"] = "allowed"
    approval_required: bool = False


class Skill(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    instructions: str
    profile: ExecutionProfile = ExecutionProfile()
