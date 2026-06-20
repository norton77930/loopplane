"""Unit 065: the backend slash-command registry over a fake host.

The registry dispatches a leading-/ command to a handler that maps to an EXISTING
host seam; an unknown command / a failing seam -> a normalized result (never raises);
a non-command line is not dispatched. Public-safe; read-only except /compact.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from loopplane.commands import CommandContext, CommandResult, default_registry


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
    ) -> None:
        self._session = session
        self._monthly = monthly
        self._memory = tuple(memory)
        self._compacted = compacted
        self._raise_session = raise_session
        self._raise_compact = raise_compact

    def session_cost(self, session_id: str) -> Decimal | None:
        if self._raise_session:
            raise KeyError(session_id)
        return self._session

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        return self._monthly

    def inspect_memory(self, query: str | None = None) -> tuple[_Entry, ...]:
        return self._memory

    def compact_session(self, session_id: str) -> bool:
        if self._raise_compact:
            raise KeyError(session_id)
        return self._compacted


def _ctx(
    host: _FakeHost, *, session_id: str | None = "s1", models=()
) -> CommandContext:
    return CommandContext(
        host=host, principal_id="alice", session_id=session_id, models=tuple(models)
    )


def test_cost_session_and_monthly() -> None:
    host = _FakeHost(session=Decimal("0.003000"), monthly=Decimal("1.50"))
    result = default_registry().dispatch("/cost", _ctx(host))
    assert result.kind == "ok"
    assert "session: 0.003000" in result.text
    assert "monthly: 1.50" in result.text


def test_cost_not_tracked_is_clean() -> None:
    host = _FakeHost(session=None, monthly=None)
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
    host = _FakeHost(raise_session=True, monthly=Decimal("0"))
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
    result = default_registry().dispatch("/compact", _ctx(_FakeHost(compacted=True)))
    assert result == CommandResult(kind="ok", text="compacted")


def test_compact_nothing_to_compact() -> None:
    result = default_registry().dispatch("/compact", _ctx(_FakeHost(compacted=False)))
    assert result == CommandResult(kind="ok", text="nothing to compact")


def test_compact_no_session_is_clean_error() -> None:
    result = default_registry().dispatch("/compact", _ctx(_FakeHost(), session_id=None))
    assert result.kind == "error"
    assert "no active session" in result.text


def test_compact_unknown_session_is_clean_error() -> None:
    result = default_registry().dispatch(
        "/compact", _ctx(_FakeHost(raise_compact=True))
    )
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
