"""Unit 065: the backend slash-command registry over a fake host.

The registry dispatches a leading-/ command to a handler that maps to an EXISTING
host seam; an unknown command / a failing seam -> a normalized result (never raises);
a non-command line is not dispatched. Public-safe; read-only except /compact.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from loopplane.commands import (
    CommandContext,
    CommandRegistry,
    CommandResult,
    default_registry,
)


@dataclass(frozen=True)
class _Entry:
    name: str
    snippet: str


class _FakeHost:
    def __init__(
        self,
        *,
        session: Decimal | None = None,
        monthly: Decimal | None = None,
        memory: Sequence[_Entry] = (),
        compacted: bool = True,
        raise_session: bool = False,
        raise_compact: bool = False,
        sessions: Sequence[object] = (),
        controls: object | None = None,
        history: Sequence[object] = (),
    ) -> None:
        self._session = session
        self._monthly = monthly
        self._memory = tuple(memory)
        self._compacted = compacted
        self._raise_session = raise_session
        self._raise_compact = raise_compact
        self._sessions = tuple(sessions)
        self._controls = controls
        self._history = tuple(history)
        self.calls: list[str] = []

    def session_cost(self, session_id: str) -> Decimal | None:
        if self._raise_session:
            raise KeyError(session_id)
        return self._session

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        return self._monthly

    def inspect_memory(self, query: str | None = None) -> tuple[_Entry, ...]:
        return self._memory

    def compact_session(self, session_id: str) -> bool:
        self.calls.append("compact_session")
        if self._raise_compact:
            raise KeyError(session_id)
        return self._compacted

    def list_sessions(self) -> tuple[object, ...]:
        self.calls.append("list_sessions")
        return self._sessions

    def agent_controls(self, session_id: str) -> object:
        self.calls.append("agent_controls")
        if self._controls is None:
            raise KeyError(session_id)
        return self._controls

    def history_snapshot(self, session_id: str) -> tuple[object, ...]:
        self.calls.append("history_snapshot")
        return self._history


def _ctx(
    host: _FakeHost, *, session_id: str | None = "s1", models=()
) -> CommandContext:
    return CommandContext(
        host=host, principal_id="alice", session_id=session_id, models=tuple(models)
    )


def test_cost_session_and_monthly() -> None:
    host = _FakeHost(
        sessions=(_Summary("s1"),),
        session=Decimal("0.003000"),
        monthly=Decimal("1.50"),
    )
    result = default_registry().dispatch("/cost", _ctx(host))
    assert result.kind == "ok"
    assert "session: 0.003000" in result.text
    assert "monthly: 1.50" in result.text


def test_cost_not_tracked_is_clean() -> None:
    host = _FakeHost(sessions=(_Summary("s1"),), session=None, monthly=None)
    result = default_registry().dispatch("/cost", _ctx(host))
    assert result.kind == "ok"
    assert "session: not tracked" in result.text
    assert "monthly: not tracked" in result.text


def test_cost_no_session_only_monthly() -> None:
    host = _FakeHost(monthly=Decimal("2"))
    result = default_registry().dispatch("/cost", _ctx(host, session_id=None))
    assert "session:" not in result.text
    assert "monthly: 2" in result.text


def test_cost_unknown_session_does_not_crash() -> None:
    """The session is the caller's, but the cost seam itself raises."""

    host = _FakeHost(
        sessions=(_Summary("s1"),), raise_session=True, monthly=Decimal("0")
    )
    result = default_registry().dispatch("/cost", _ctx(host))
    assert result.kind == "ok"
    assert "session: not tracked" in result.text


def test_model_lists_available() -> None:
    result = default_registry().dispatch("/model", _ctx(_FakeHost(), models=("a", "b")))
    assert result.kind == "ok"
    assert "- a" in result.text and "- b" in result.text


def test_model_none_advertised() -> None:
    result = default_registry().dispatch("/model", _ctx(_FakeHost()))
    assert result.kind == "ok"
    assert "none advertised" in result.text


def test_memory_lists_entries() -> None:
    host = _FakeHost(memory=(_Entry("note", "a snippet"),))
    result = default_registry().dispatch("/memory", _ctx(host))
    assert result.kind == "ok"
    assert "note" in result.text and "a snippet" in result.text


def test_memory_none() -> None:
    result = default_registry().dispatch("/memory", _ctx(_FakeHost()))
    assert result.kind == "ok"
    assert "no memory entries" in result.text


def test_compact_compacts() -> None:
    host = _FakeHost(sessions=(_Summary("s1"),), compacted=True)
    result = default_registry().dispatch("/compact", _ctx(host))
    assert result == CommandResult(kind="ok", text="compacted")


def test_compact_nothing_to_compact() -> None:
    host = _FakeHost(sessions=(_Summary("s1"),), compacted=False)
    result = default_registry().dispatch("/compact", _ctx(host))
    assert result == CommandResult(kind="ok", text="nothing to compact")


def test_compact_no_session_is_clean_error() -> None:
    result = default_registry().dispatch("/compact", _ctx(_FakeHost(), session_id=None))
    assert result.kind == "error"
    assert "no active session" in result.text


def test_compact_unknown_session_is_clean_error() -> None:
    host = _FakeHost(sessions=(_Summary("s1"),), raise_compact=True)
    result = default_registry().dispatch("/compact", _ctx(host))
    assert result.kind == "error"
    assert "session not found" in result.text


def test_unknown_command() -> None:
    result = default_registry().dispatch("/bogus", _ctx(_FakeHost()))
    assert result.kind == "unknown"
    assert "/bogus" in result.text


def test_non_command_line() -> None:
    result = default_registry().dispatch("just talking", _ctx(_FakeHost()))
    assert result.kind == "unknown"


def test_memory_passes_args_as_query() -> None:
    seen: list[str | None] = []

    class _Probe(_FakeHost):
        def inspect_memory(self, query: str | None = None) -> tuple[_Entry, ...]:
            seen.append(query)
            return ()

    default_registry().dispatch("/memory needle", _ctx(_Probe()))
    assert seen == ["needle"]


# --- 079: descriptors, new commands, and the remote-safety policy -------------


@dataclass(frozen=True)
class _Summary:
    session_id: str
    label: str | None = None
    principal_id: str | None = None


@dataclass(frozen=True)
class _Mode:
    id: str


@dataclass(frozen=True)
class _ActiveRun:
    plan_active: bool


@dataclass(frozen=True)
class _Permission:
    default_mode: str | None
    selectable_modes: tuple[_Mode, ...]
    plan_entry_available: bool
    active_run: _ActiveRun | None


@dataclass(frozen=True)
class _Controls:
    permission: _Permission


@dataclass(frozen=True)
class _HistoryEntry:
    role: str
    blocks: tuple[object, ...]


def test_every_command_is_described_with_a_summary_and_a_classification() -> None:
    described = default_registry().describe()
    assert [item.name for item in described] == sorted(item.name for item in described)
    assert {item.name for item in described} == {
        "compact",
        "cost",
        "help",
        "history",
        "memory",
        "model",
        "permission",
        "sessions",
    }
    assert all(item.summary for item in described)


def test_only_compact_is_not_remote_safe() -> None:
    described = default_registry().describe()
    unsafe = {item.name for item in described if not item.remote_safe}
    assert unsafe == {"compact"}


def test_help_lists_every_command_locally() -> None:
    result = default_registry().dispatch("/help", _ctx(_FakeHost()))
    assert result.kind == "ok"
    for name in ("cost", "compact", "help", "history", "memory", "model"):
        assert f"/{name}" in result.text


def test_help_hides_non_remote_safe_commands_remotely() -> None:
    ctx = replace(_ctx(_FakeHost()), remote=True)
    result = default_registry().dispatch("/help", ctx)
    assert result.kind == "ok"
    assert "/compact" not in result.text
    assert "/cost" in result.text


def test_sessions_lists_only_the_callers_own() -> None:
    host = _FakeHost(
        sessions=(
            _Summary("mine", label="a chat", principal_id="alice"),
            _Summary("theirs", principal_id="bob"),
            _Summary("unowned", principal_id=None),
        )
    )
    result = default_registry().dispatch("/sessions", _ctx(host))
    assert result.kind == "ok"
    assert "mine" in result.text
    assert "a chat" in result.text
    assert "unowned" in result.text
    assert "theirs" not in result.text


def test_sessions_empty() -> None:
    result = default_registry().dispatch("/sessions", _ctx(_FakeHost()))
    assert result.kind == "ok"
    assert "no sessions" in result.text


def test_permission_shows_posture_without_rule_expressions() -> None:
    host = _FakeHost(
        sessions=(_Summary("s1", principal_id="alice"),),
        controls=_Controls(
            permission=_Permission(
                default_mode="ask",
                selectable_modes=(_Mode("ask"), _Mode("plan")),
                plan_entry_available=True,
                active_run=_ActiveRun(plan_active=False),
            )
        ),
    )
    result = default_registry().dispatch("/permission", _ctx(host))
    assert result.kind == "ok"
    assert "mode: ask" in result.text
    assert "selectable: ask, plan" in result.text
    assert "plan available: yes" in result.text
    assert "plan active: no" in result.text


def test_permission_without_a_session_is_a_clean_error() -> None:
    result = default_registry().dispatch(
        "/permission", _ctx(_FakeHost(), session_id=None)
    )
    assert result.kind == "error"
    assert "no active session" in result.text


def test_permission_unknown_session_is_a_clean_error() -> None:
    result = default_registry().dispatch("/permission", _ctx(_FakeHost()))
    assert result.kind == "error"
    assert "session not found" in result.text


def test_history_shows_shape_only() -> None:
    host = _FakeHost(
        sessions=(_Summary("s1", principal_id="alice"),),
        history=(
            _HistoryEntry(role="user", blocks=(object(),)),
            _HistoryEntry(role="assistant", blocks=(object(), object())),
        ),
    )
    result = default_registry().dispatch("/history", _ctx(host))
    assert result.kind == "ok"
    assert "- user: 1 block(s)" in result.text
    assert "- assistant: 2 block(s)" in result.text


def test_history_without_a_session_is_a_clean_error() -> None:
    result = default_registry().dispatch("/history", _ctx(_FakeHost(), session_id=None))
    assert result.kind == "error"


def test_remote_refuses_a_non_remote_safe_command_without_touching_the_host() -> None:
    host = _FakeHost(compacted=True)
    ctx = replace(_ctx(host), remote=True)
    result = default_registry().dispatch("/compact", ctx)
    assert result.kind == "error"
    assert "not available over a remote connection" in result.text
    # The refusal happens before the handler runs, so no seam was called.
    assert host.calls == []


def test_remote_allows_a_remote_safe_command() -> None:
    host = _FakeHost(
        sessions=(_Summary("s1"),), session=Decimal("1"), monthly=Decimal("2")
    )
    ctx = replace(_ctx(host), remote=True)
    result = default_registry().dispatch("/cost", ctx)
    assert result.kind == "ok"
    assert "monthly: 2" in result.text


def test_context_is_local_by_default() -> None:
    assert CommandContext(host=_FakeHost(), principal_id="alice").remote is False


def test_registering_without_the_new_keywords_keeps_pre_079_defaults() -> None:
    registry = CommandRegistry()
    registry.register("thing", lambda ctx: CommandResult(kind="ok", text="ran"))
    described = registry.describe()
    assert described[0].remote_safe is True
    assert described[0].summary == ""
    assert registry.dispatch("/thing", _ctx(_FakeHost())).text == "ran"


def test_one_registry_answers_identically_on_every_surface() -> None:
    """SC-005: the same command line under a CLI-shaped and a web-shaped context
    returns the same result, because there is one definition."""

    host = _FakeHost(session=Decimal("0.5"), monthly=Decimal("3"))
    registry = default_registry()
    cli_ctx = CommandContext(host=host, principal_id="alice", session_id="s1")
    web_ctx = CommandContext(
        host=host, principal_id="alice", session_id="s1", models=()
    )
    assert registry.dispatch("/cost", cli_ctx) == registry.dispatch("/cost", web_ctx)
    assert registry.dispatch("/help", cli_ctx) == registry.dispatch("/help", web_ctx)


# --- 079 remediation: the handlers' own ownership check (second layer) --------


def test_history_refuses_another_principals_session() -> None:
    """The second layer: even if a host forgets its own gate, the handler will
    not read a conversation the caller does not own."""

    host = _FakeHost(
        sessions=(_Summary("s1", principal_id="bob"),),
        history=(_HistoryEntry(role="user", blocks=(object(),)),),
    )
    result = default_registry().dispatch("/history", _ctx(host))
    assert result.kind == "error"
    assert result.text == "session not found"
    assert "history_snapshot" not in host.calls


def test_permission_refuses_another_principals_session() -> None:
    host = _FakeHost(
        sessions=(_Summary("s1", principal_id="bob"),),
        controls=_Controls(
            permission=_Permission(
                default_mode="ask",
                selectable_modes=(),
                plan_entry_available=False,
                active_run=None,
            )
        ),
    )
    result = default_registry().dispatch("/permission", _ctx(host))
    assert result.kind == "error"
    assert result.text == "session not found"
    assert "agent_controls" not in host.calls


def test_a_missing_session_and_a_foreign_one_look_the_same() -> None:
    foreign = _FakeHost(sessions=(_Summary("s1", principal_id="bob"),))
    missing = _FakeHost(sessions=())
    assert default_registry().dispatch("/history", _ctx(foreign)) == (
        default_registry().dispatch("/history", _ctx(missing))
    )


def test_a_session_without_a_principal_is_readable_by_its_local_host() -> None:
    """The terminal and the sidecar have no principals, so their sessions carry
    none; those hosts must still be able to read their own conversation."""

    host = _FakeHost(
        sessions=(_Summary("s1", principal_id=None),),
        history=(_HistoryEntry(role="user", blocks=(object(),)),),
    )
    result = default_registry().dispatch("/history", _ctx(host))
    assert result.kind == "ok"
    assert "1 block(s)" in result.text


def test_every_session_scoped_command_is_declared() -> None:
    """The webapi ownership gate is driven by this declaration, so it is the
    thing that must not drift."""

    scoped = default_registry().session_scoped_names()
    assert scoped == {"cost", "compact", "history", "permission"}
    described = {d.name for d in default_registry().describe() if d.session_scoped}
    assert described == scoped


def test_registering_without_session_scoped_defaults_to_false() -> None:
    registry = CommandRegistry()
    registry.register("thing", lambda ctx: CommandResult(kind="ok", text="ran"))
    assert registry.session_scoped_names() == frozenset()
    assert registry.describe()[0].session_scoped is False


def test_help_listing_is_shared_with_hosts_that_answer_it_themselves() -> None:
    """`format_command_listing` is what lets the remote terminal answer /help
    locally and still produce exactly the registry's text (FR-022)."""

    from loopplane.commands import format_command_listing

    registry = default_registry()
    local = registry.dispatch("/help", _ctx(_FakeHost()))
    assert local.text == format_command_listing(registry.describe())

    remote_ctx = replace(_ctx(_FakeHost()), remote=True)
    remote = registry.dispatch("/help", remote_ctx)
    assert remote.text == format_command_listing(registry.describe(), remote=True)
    assert "/compact" not in remote.text


def test_every_session_scoped_command_carries_the_second_layer() -> None:
    """FR-042 as an executable claim: the layer is universal, not just on the
    two commands 079 added. `/compact` — the only irreversible one — is the
    last place that should be missing it."""

    foreign = _Summary("s1", principal_id="bob")
    for name in sorted(default_registry().session_scoped_names()):
        host = _FakeHost(
            sessions=(foreign,),
            session=Decimal("1"),
            monthly=Decimal("2"),
            compacted=True,
            controls=_Controls(
                permission=_Permission(
                    default_mode="ask",
                    selectable_modes=(),
                    plan_entry_available=False,
                    active_run=None,
                )
            ),
            history=(_HistoryEntry(role="user", blocks=()),),
        )
        result = default_registry().dispatch(f"/{name}", _ctx(host))
        assert result.kind == "error", name
        assert result.text == "session not found", name
        # And nothing was read or mutated on the way to refusing.
        assert host.calls == ["list_sessions"], (name, host.calls)
