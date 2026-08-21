"""The terminal's interactive core (079 US1, US2, US3).

One conversation across turns, permission requests and questions answered from
the terminal, and an interrupt that stops a turn without ending the conversation.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from loopplane.cli import chat_loop, resume_loop
from loopplane.cli.session import INTERRUPTED_NOTICE
from tests.cli_helpers import (
    asking_host,
    gated_host,
    interrupting_host,
    scripted_host,
    sigint_host,
)

pytestmark = pytest.mark.anyio


# --- US1: one continuing conversation ---------------------------------------


async def test_every_turn_belongs_to_one_conversation() -> None:
    host = scripted_host("first reply", "second reply")
    out = io.StringIO()
    await chat_loop(host, ["hello", "again", "quit"], out)
    text = out.getvalue()
    assert "first reply" in text
    assert "second reply" in text
    # One conversation, not one per turn: the host recorded a single session.
    assert len(host.list_sessions()) == 1


async def test_the_second_turn_carries_the_first_turns_context() -> None:
    host = scripted_host("noted", "recalled")
    out = io.StringIO()
    await chat_loop(
        host, ["my favourite colour is teal", "what did I say", "quit"], out
    )
    session_id = host.list_sessions()[0].session_id
    roles = [entry.role for entry in host.history_snapshot(session_id)]
    # Both user turns and both assistant replies live in the same history.
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


async def test_conversation_closes_cleanly_on_end_of_input() -> None:
    host = scripted_host("only reply")
    out = io.StringIO()
    await chat_loop(host, ["hi"], out)  # the iterable ends -> EOF
    assert "only reply" in out.getvalue()
    assert len(host.list_sessions()) == 1


async def test_resume_continues_the_stored_conversation(tmp_path: Path) -> None:
    store = tmp_path / "sessions"
    host = scripted_host("first", "second", store=store)
    out = io.StringIO()
    await chat_loop(host, ["hello", "quit"], out)
    session_id = host.list_sessions()[0].session_id
    await host.aclose()

    resumed = scripted_host("continued", store=store)
    resumed_out = io.StringIO()
    await resume_loop(resumed, session_id, ["and again", "quit"], resumed_out)
    assert "continued" in resumed_out.getvalue()
    # Same conversation, not a new one.
    assert [s.session_id for s in resumed.list_sessions()] == [session_id]
    await resumed.aclose()


async def test_resume_without_a_store_raises_for_the_caller_to_render() -> None:
    host = scripted_host("unused")
    out = io.StringIO()
    with pytest.raises((KeyError, RuntimeError)):
        await resume_loop(host, "no-such-session", ["hello", "quit"], out)


# --- US2: approvals and questions --------------------------------------------


async def test_approval_is_rendered_safely_and_answered_from_the_next_line() -> None:
    host = gated_host()
    out = io.StringIO()
    await chat_loop(host, ["do it", "y", "quit"], out)
    text = out.getvalue()
    assert "[approve] gated" in text
    assert "the gated tool ran" not in text  # raw tool output is never rendered
    # The approval prompt lands between the tool's start and its outcome, which
    # is exactly when the runtime asks for it.
    assert "[tool gated]" in text
    assert "success" in text


async def test_denying_an_approval_stops_the_tool() -> None:
    host = gated_host()
    out = io.StringIO()
    await chat_loop(host, ["do it", "n", "quit"], out)
    text = out.getvalue()
    assert "[approve] gated" in text
    assert "failure" in text  # the denied call completes as a failure


async def test_session_scope_does_not_ask_again() -> None:
    host = gated_host(calls=2)
    out = io.StringIO()
    # "a" allows for the rest of the conversation, so the second turn's call
    # needs no answer line of its own.
    await chat_loop(host, ["first", "a", "second", "quit"], out)
    assert out.getvalue().count("[approve] gated") == 1


async def test_once_scope_asks_again_on_the_next_request() -> None:
    host = gated_host(calls=2)
    out = io.StringIO()
    await chat_loop(host, ["first", "y", "second", "y", "quit"], out)
    assert out.getvalue().count("[approve] gated") == 2


async def test_unrecognized_approval_answer_denies_once() -> None:
    host = gated_host()
    out = io.StringIO()
    await chat_loop(host, ["do it", "maybe", "quit"], out)
    assert "failure" in out.getvalue()


async def test_a_question_is_answered_from_the_next_line() -> None:
    host = asking_host()
    out = io.StringIO()
    await chat_loop(host, ["ask me", "teal", "quit"], out)
    text = out.getvalue()
    assert "[question] which colour?" in text
    assert "- teal" in text  # the options are shown
    assert "thanks" in text  # the turn continued after the answer


async def test_ending_with_a_request_pending_does_not_hang() -> None:
    host = gated_host()
    out = io.StringIO()
    # Input ends while the approval is pending: the handler sees end-of-input,
    # denies, and the run terminates rather than waiting forever.
    await chat_loop(host, ["do it"], out)
    assert "[approve] gated" in out.getvalue()
    assert "[run " in out.getvalue()


# --- US3: interrupting a running turn ----------------------------------------


async def test_interrupt_stops_the_turn_and_keeps_the_conversation() -> None:
    host = interrupting_host(then="still here")
    out = io.StringIO()
    await chat_loop(host, ["long one", "hello again", "quit"], out)
    text = out.getvalue()
    assert INTERRUPTED_NOTICE.strip() in text
    assert "still here" in text  # the next line ran in the same conversation
    assert len(host.list_sessions()) == 1


async def test_interrupt_before_the_turns_work_begins_is_also_caught() -> None:
    # A KeyboardInterrupt raised on the very first model call is the pre-turn
    # case FR-011 names; the mid-stream case is covered above by the same
    # scripted failure arriving after the run has started.
    host = interrupting_host(then="recovered")
    out = io.StringIO()
    await chat_loop(host, ["first", "second", "quit"], out)
    assert INTERRUPTED_NOTICE.strip() in out.getvalue()
    assert "recovered" in out.getvalue()


async def test_interrupt_while_an_approval_is_pending_leaves_nothing_waiting() -> None:
    host = gated_host()
    out = io.StringIO()

    def lines() -> object:
        yield "do it"
        raise KeyboardInterrupt

    await chat_loop(host, lines(), out)
    text = out.getvalue()
    assert "[approve] gated" in text
    assert INTERRUPTED_NOTICE.strip() in text


# --- US4: the new commands against a real host -------------------------------


async def test_new_commands_work_against_a_real_host() -> None:
    host = scripted_host("a reply")
    out = io.StringIO()
    await chat_loop(host, ["hello", "/help", "/sessions", "/history", "quit"], out)
    text = out.getvalue()
    assert "/permission" in text  # /help listed the real registry
    assert "commands:" in text
    session_id = host.list_sessions()[0].session_id
    assert session_id in text  # /sessions found the caller's own conversation
    assert "block(s)" in text  # /history rendered shape, not content


async def test_permission_command_reads_the_real_projection() -> None:
    host = scripted_host("a reply")
    out = io.StringIO()
    await chat_loop(host, ["hello", "/permission", "quit"], out)
    text = out.getvalue()
    assert "mode: " in text
    assert "plan available: " in text


async def test_history_command_never_renders_message_content() -> None:
    host = scripted_host("the assistant said something private")
    out = io.StringIO()
    await chat_loop(host, ["a secret of mine", "/history", "quit"], out)
    # The reply is streamed (that is the conversation), but /history's own
    # output is shape only — it must not repeat the user's line back.
    history_output = out.getvalue().split("block(s)")[0]
    assert "a secret of mine" not in history_output


# --- US3 remediation: a REAL Ctrl-C, not an injected KeyboardInterrupt --------


async def test_a_real_sigint_cancels_the_turn_and_keeps_the_conversation() -> None:
    """The interrupt path a terminal actually takes.

    A real Ctrl-C under `anyio.run` reaches the await as CancelledError, so the
    old `except KeyboardInterrupt` never fired outside tests. The conversation
    now installs its own handler, which asks the runtime to cancel.
    """

    host = sigint_host(then="still here")
    out = io.StringIO()
    await chat_loop(host, ["start something", "and again", "quit"], out)
    text = out.getvalue()
    assert INTERRUPTED_NOTICE.strip() in text
    # The conversation survived: the next line ran in the same session.
    assert "still here" in text
    assert len(host.list_sessions()) == 1


async def test_the_interrupt_watch_restores_the_previous_handler() -> None:
    import signal

    before = signal.getsignal(signal.SIGINT)
    await chat_loop(scripted_host("a reply"), ["hello", "quit"], io.StringIO())
    assert signal.getsignal(signal.SIGINT) is before


async def test_an_interrupt_does_not_leak_into_the_next_turn() -> None:
    """The regression that the first design shipped: cancelling after the turn
    had already ended armed a fresh signal and killed the following turn."""

    host = sigint_host(then="second turn ran")
    out = io.StringIO()
    await chat_loop(host, ["first", "second", "third", "quit"], out)
    text = out.getvalue()
    # Exactly one turn was cancelled — the interrupted one — and the two that
    # follow both ran to completion. The old design failed here: cancelling
    # after the turn was already over armed a fresh signal, so the NEXT turn
    # came back cancelled too.
    assert text.count(INTERRUPTED_NOTICE.strip()) == 1
    assert text.count("[run cancelled") == 1
    assert text.count("[run natural-completion") == 2
