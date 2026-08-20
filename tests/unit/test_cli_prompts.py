"""Unit tests for the CLI's shared input source (079 T003, T005; FR-006, FR-007).

One line source feeds turns, approval answers, and question answers, so the whole
interactive loop stays drivable from a list of strings.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import threading

import pytest

from loopplane.cli.prompts import (
    LineSource,
    interrupt_watch,
    parse_approval_answer,
    question_answer,
)


def test_line_source_yields_lines_then_reports_exhaustion() -> None:
    source = LineSource(["first", "second"])
    assert source.next_line() == "first"
    assert source.exhausted is False
    assert source.next_line() == "second"
    assert source.next_line() is None
    assert source.exhausted is True


def test_line_source_distinguishes_blank_line_from_end_of_input() -> None:
    source = LineSource(["", "after"])
    assert source.next_line() == ""  # a blank line is a value, not the end
    assert source.exhausted is False
    assert source.next_line() == "after"
    assert source.next_line() is None
    assert source.exhausted is True


@pytest.mark.parametrize(
    ("line", "allow", "scope"),
    [
        ("y", True, "once"),
        ("yes", True, "once"),
        ("Y", True, "once"),
        ("n", False, "once"),
        ("no", False, "once"),
        ("a", True, "session"),
        ("always", True, "session"),
        ("never", False, "session"),
    ],
)
def test_parse_approval_answer_maps_each_documented_answer(
    line: str, allow: bool, scope: str
) -> None:
    answer = parse_approval_answer(line)
    assert answer.allow is allow
    assert answer.scope == scope


@pytest.mark.parametrize("line", ["", "   ", "maybe", "yolo", None])
def test_unrecognized_approval_answer_denies_once(line: str | None) -> None:
    answer = parse_approval_answer(line)
    assert answer.allow is False
    assert answer.scope == "once"


def test_question_answer_trims_and_never_blocks_on_end_of_input() -> None:
    assert question_answer("  an answer  ") == "an answer"
    assert question_answer("") == ""
    assert question_answer(None) == ""


# --- why interrupt_watch exists, as an executable claim ----------------------


_RUNNER_PROBE = """
import signal, sys, threading, time
import anyio

seen = []

async def main():
    try:
        await anyio.sleep(10)
    except KeyboardInterrupt:
        seen.append("KeyboardInterrupt")
    except BaseException as exc:
        seen.append(type(exc).__name__)
        raise

threading.Thread(
    target=lambda: (time.sleep(0.6), signal.raise_signal(signal.SIGINT)),
    daemon=True,
).start()
try:
    anyio.run(main)
except BaseException as exc:
    seen.append("escaped:" + type(exc).__name__)
print(";".join(seen))
"""


def test_a_real_ctrl_c_does_not_reach_an_await_as_keyboardinterrupt() -> None:
    """The reason `interrupt_watch` exists, kept executable.

    Under `anyio.run` the asyncio runner cancels the main task on SIGINT, so an
    `except KeyboardInterrupt` around a turn never fires from a real terminal.
    If this ever stops being true, the comment in `interrupt_watch` is stale and
    the design can be simplified — this test is what will say so.

    Runs in a subprocess because it installs and fires signal handlers.
    """

    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER_PROBE],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    observed = completed.stdout.strip()
    assert "CancelledError" in observed, observed
    assert not observed.startswith("KeyboardInterrupt"), observed


def test_interrupt_watch_installs_and_restores_the_handler() -> None:
    before = signal.getsignal(signal.SIGINT)
    calls: list[str] = []
    with interrupt_watch(lambda: calls.append("cancel")) as state:
        assert state.installed is True
        assert signal.getsignal(signal.SIGINT) is not before
        signal.raise_signal(signal.SIGINT)
        assert calls == ["cancel"]
        assert state.take() is True
        assert state.take() is False  # consumed once per interrupt
    assert signal.getsignal(signal.SIGINT) is before


def test_interrupt_watch_is_inert_off_the_main_thread() -> None:
    """An embedded host or a worker thread cannot install handlers; the watch
    must degrade rather than fail the conversation."""

    outcome: list[bool] = []

    def body() -> None:
        with interrupt_watch(lambda: None) as state:
            outcome.append(state.installed)

    thread = threading.Thread(target=body)
    thread.start()
    thread.join(timeout=10)
    assert outcome == [False]
