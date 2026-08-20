"""Unit tests for CLI provider selection (T003; FR-005, FR-006)."""

from __future__ import annotations

from loopplane.cli.providers import DemoModel, select_model
from loopplane.model import ModelBoundary, ScriptedModel


def test_no_env_selects_the_demo_model() -> None:
    model = select_model({})
    assert isinstance(model, DemoModel)
    assert isinstance(model, ModelBoundary)


def test_env_builder_is_imported_and_used() -> None:
    model = select_model({"LOOPPLANE_MODEL": "tests.cli_helpers:build_fake_model"})
    assert isinstance(model, ScriptedModel)


def test_bad_reference_falls_back_to_the_demo_model() -> None:
    assert isinstance(
        select_model({"LOOPPLANE_MODEL": "no.such.module:thing"}), DemoModel
    )
    assert isinstance(select_model({"LOOPPLANE_MODEL": "no-colon-here"}), DemoModel)


# --- 079 remediation: the idle-prompt Ctrl-C window --------------------------


def test_dispatch_turns_an_idle_ctrl_c_into_a_clean_exit() -> None:
    """The interactive loop installs its interrupt handler only while a turn is
    running, so Ctrl-C at an idle prompt reaches the runtime's own handling and
    surfaces here. It must end the way this command always has — a newline and a
    clean exit — not a traceback.

    (That the runtime raises KeyboardInterrupt out of `anyio.run` rather than
    delivering it to the await is itself pinned by
    `tests/unit/test_cli_prompts.py::test_a_real_ctrl_c_does_not_reach_an_await_as_keyboardinterrupt`.)
    """

    import io as _io

    from loopplane.cli import app as cli_app

    def boom(*args: object, **kwargs: object) -> int:
        raise KeyboardInterrupt

    original = cli_app.anyio.run
    cli_app.anyio.run = boom  # type: ignore[assignment]
    try:
        out = _io.StringIO()
        code = cli_app.dispatch(["chat"], out)
    finally:
        cli_app.anyio.run = original  # type: ignore[assignment]

    assert code == 0
    assert out.getvalue() == "\n"
