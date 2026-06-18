"""Smoke test: every credential-free example under ``examples/`` runs to exit 0.

Guards against shipping a broken public example. CI's ``mypy`` only checks ``src``
and pytest's collection is ``tests/``, so files under ``examples/`` are otherwise
never executed or type-checked — a stale example (e.g. one not updated for an API
change) can ship green. This runs each credential-free example as a subprocess and
asserts a clean exit, capturing its output on failure.

The two provider quickstarts (Anthropic/OpenAI, unit 020) are excluded here: they
drive a real model and are covered by the opt-in live tests (``tests/live``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES_DIR = _REPO_ROOT / "examples"

# Provider quickstarts need a real API key; covered by tests/live instead.
_CREDENTIAL_REQUIRED = {"anthropic_quickstart.py", "openai_quickstart.py"}


def _credential_free_examples() -> list[Path]:
    return sorted(
        p for p in _EXAMPLES_DIR.glob("*.py") if p.name not in _CREDENTIAL_REQUIRED
    )


def test_examples_present() -> None:
    # Guard against a silent pass if discovery breaks (empty parametrization).
    assert len(_credential_free_examples()) >= 10


@pytest.mark.parametrize("example", _credential_free_examples(), ids=lambda p: p.name)
def test_example_runs_clean(example: Path) -> None:
    # A stray LOOPPLANE_MODEL in the runner's environment would push a
    # credential-free example onto a real provider; drop it so the example uses
    # its own built-in demo/scripted model.
    env = dict(os.environ)
    env.pop("LOOPPLANE_MODEL", None)

    result = subprocess.run(
        [sys.executable, str(example)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=50,
    )

    assert result.returncode == 0, (
        f"{example.name} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
