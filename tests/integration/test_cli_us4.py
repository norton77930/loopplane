"""US4: use a real model when configured (T012; FR-006, SC-003)."""

from __future__ import annotations

import io

import pytest

from loopplane.cli import dispatch


def test_run_uses_the_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOPPLANE_MODEL", "tests.cli_helpers:build_fake_model")
    out = io.StringIO()
    assert dispatch(["run", "hi"], out) == 0
    assert "from a real builder" in out.getvalue()


def test_run_falls_back_to_the_demo_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOOPPLANE_MODEL", raising=False)
    out = io.StringIO()
    dispatch(["run", "hi"], out)
    assert "demo model" in out.getvalue().lower()
