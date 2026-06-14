"""US3: conduct an interactive session from the console — submit and answer a
pending approval (in-process) (FR-020-FR-022). In-process only.

The interactive approval round-trip is exercised **directly**: a session opened
with an injected ``on_approval`` handler reaches its outcome on ``submit`` (no
transport, so unit 011's buffering-client limitation does not apply). "Cancel
never hangs on a pending approval" is the ``Session.cancel()`` guarantee covered
by the Phase-2 host suite (``test_cancel_resolves_a_pending_approval_without_hanging``),
which the studio's ``cancel`` delegates to; the registry close + host-free are
covered by US2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.host import ApprovalPolicy
from loopplane.studio import ErrorView, RunResultView, StudioHost
from tests.studio_helpers import (
    auto_approve,
    build_test_host,
    multi_text_model,
    tool_then_text_model,
)


@pytest.mark.anyio
async def test_interactive_submit_with_approval(tmp_path: Path) -> None:
    host = build_test_host(
        tmp_path,
        model=tool_then_text_model(),
        approval=ApprovalPolicy(ask=frozenset({"echo"})),
    )
    async with StudioHost(host) as studio:
        session_id = await studio.open_session(on_approval=auto_approve)
        assert isinstance(session_id, str)

        outcome = await studio.submit(session_id, "go")

        # The echo tool's approval was answered in-process by the injected
        # handler, so the run reaches completion.
        assert isinstance(outcome, RunResultView)
        assert outcome.termination_reason == "natural-completion"
        await studio.cancel(session_id)


@pytest.mark.anyio
async def test_answer_and_submit_unknown_are_explicit(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    async with StudioHost(host) as studio:
        session_id = await studio.open_session()

        # Unknown request id on a known session → False, never a crash.
        assert studio.answer_approval(session_id, "ghost", allow=True) is False
        assert studio.answer_question(session_id, "ghost", ["x"]) is False
        # Unknown session → an explicit not-found view.
        assert isinstance(studio.answer_approval("ghost", "r", allow=True), ErrorView)
        assert isinstance(await studio.submit("ghost", "x"), ErrorView)
        await studio.cancel(session_id)
