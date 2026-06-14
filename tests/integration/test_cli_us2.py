"""US2: run a one-shot prompt non-interactively (T010; FR-003, SC-002)."""

from __future__ import annotations

import io

import pytest

from loopplane.cli import dispatch


def test_run_renders_a_response_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOOPPLANE_MODEL", raising=False)
    out = io.StringIO()
    code = dispatch(["run", "hello"], out)
    assert code == 0
    text = out.getvalue()
    assert "demo model" in text.lower()
    assert "[run natural-completion" in text


def test_run_missing_prompt_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        dispatch(["run"], io.StringIO())
    assert exc.value.code == 2


def test_no_command_prints_help_and_returns_two() -> None:
    out = io.StringIO()
    assert dispatch([], out) == 2
