"""US5: a safe, thin command (T013; FR-008, FR-009)."""

from __future__ import annotations

import io

import pytest

from loopplane.cli import run_once
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedFailure, ScriptedModel
from tests.cli_helpers import scripted_host

pytestmark = pytest.mark.anyio


async def test_normal_output_is_public_safe() -> None:
    host = scripted_host("a clean response")
    out = io.StringIO()
    await run_once(host, "hi", out)
    text = out.getvalue()
    assert "a clean response" in text
    assert "[run natural-completion" in text  # only assistant text + a metadata line


async def test_model_failure_renders_a_public_safe_outcome() -> None:
    model = ScriptedModel(
        script=[ScriptedFailure(error=RuntimeError("boom-secret-detail"))],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(RuntimeConfig(model=model))
    out = io.StringIO()
    await run_once(host, "hi", out)
    text = out.getvalue()
    assert "boom-secret-detail" not in text  # no raw exception leak
    assert "[run unrecoverable-error" in text  # rendered as a normalized outcome
