"""Backend-semantic slash commands (spec 065; gap G14).

A small host command surface: a :class:`CommandRegistry` parses a leading-``/``
command and dispatches to a handler that maps to an EXISTING host seam -- ``/cost``
(064 ``session_cost``/``monthly_spend``), ``/model`` (the wiring-supplied model
list), ``/memory`` (``inspect_memory``), ``/compact`` (``compact_session``, the
loop's ``compact_history``).

Commands are a host **UX**, NOT tools: each handler calls an existing host method,
so a command never reaches the Tool Gateway (V) or the Event Bus (VI), adds no new
event/``TerminationReason``, and bumps no ``SCHEMA_VERSION``. The same registry is
shared by the CLI chat REPL and the web/API ``POST /commands`` endpoint. Dispatch
never raises (an unknown command / a failing seam -> a normalized result) and is
public-safe (no DSN/secret/another-principal's data). Three commands are read-only;
only ``/compact`` mutates, and it reuses the loop's compaction seam.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, Protocol

__all__ = [
    "CommandResult",
    "CommandContext",
    "CommandRegistry",
    "default_registry",
]


@dataclass(frozen=True)
class CommandResult:
    """A normalized, host-renderable command result (public-safe)."""

    kind: Literal["ok", "unknown", "error"]
    text: str


class _CommandHost(Protocol):
    """The existing host seams a command may read (064 + inspection + 065)."""

    def session_cost(self, session_id: str) -> Decimal | None: ...

    def monthly_spend(self, principal_id: str) -> Decimal | None: ...

    def inspect_memory(self, query: str | None = ...) -> Sequence[object]: ...

    def compact_session(self, session_id: str) -> bool: ...


@dataclass(frozen=True)
class CommandContext:
    """What a handler needs; built by each host's wiring (CLI / web-API)."""

    host: _CommandHost
    principal_id: str
    session_id: str | None = None
    models: tuple[str, ...] = ()
    args: str = ""


_Handler = Callable[[CommandContext], CommandResult]


def _fmt_usd(value: Decimal | None) -> str:
    return "not tracked" if value is None else str(value)


def _cmd_cost(ctx: CommandContext) -> CommandResult:
    lines: list[str] = []
    if ctx.session_id is not None:
        try:
            session = ctx.host.session_cost(ctx.session_id)
        except KeyError:
            session = None
        lines.append(f"session: {_fmt_usd(session)}")
    lines.append(f"monthly: {_fmt_usd(ctx.host.monthly_spend(ctx.principal_id))}")
    return CommandResult(kind="ok", text="\n".join(lines))


def _cmd_model(ctx: CommandContext) -> CommandResult:
    if not ctx.models:
        return CommandResult(kind="ok", text="available models: (none advertised)")
    listed = "\n".join(f"- {model}" for model in ctx.models)
    return CommandResult(kind="ok", text=f"available models:\n{listed}")


def _cmd_memory(ctx: CommandContext) -> CommandResult:
    entries = ctx.host.inspect_memory(ctx.args or None)
    if not entries:
        return CommandResult(kind="ok", text="no memory entries")
    rendered = "\n".join(
        f"- {getattr(entry, 'name', '?')}: {getattr(entry, 'snippet', '')}"
        for entry in entries
    )
    return CommandResult(kind="ok", text=rendered)


def _cmd_compact(ctx: CommandContext) -> CommandResult:
    if ctx.session_id is None:
        return CommandResult(kind="error", text="no active session to compact")
    try:
        compacted = ctx.host.compact_session(ctx.session_id)
    except KeyError:
        return CommandResult(kind="error", text="session not found")
    return CommandResult(
        kind="ok", text="compacted" if compacted else "nothing to compact"
    )


class CommandRegistry:
    """A registry of slash commands; ``dispatch`` parses a leading-``/`` line,
    routes to a handler, and always returns a normalized result (never raises)."""

    def __init__(self, handlers: dict[str, _Handler] | None = None) -> None:
        self._handlers: dict[str, _Handler] = dict(handlers or {})

    def register(self, name: str, handler: _Handler) -> None:
        self._handlers[name.lower()] = handler

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def is_command(self, line: str) -> bool:
        return line.lstrip().startswith("/")

    def dispatch(self, line: str, ctx: CommandContext) -> CommandResult:
        text = line.strip()
        if not text.startswith("/"):
            return CommandResult(kind="unknown", text="not a command")
        name, _, args = text[1:].strip().partition(" ")
        handler = self._handlers.get(name.lower())
        if handler is None:
            return CommandResult(kind="unknown", text=f"unknown command: /{name}")
        try:
            return handler(replace(ctx, args=args.strip()))
        except Exception:
            # Fail-safe + public-safe: never crash, never leak -- a generic error.
            return CommandResult(kind="error", text=f"/{name}: command failed")


def default_registry() -> CommandRegistry:
    """A registry with the four built-in commands (cost/model/memory/compact)."""

    return CommandRegistry(
        {
            "cost": _cmd_cost,
            "model": _cmd_model,
            "memory": _cmd_memory,
            "compact": _cmd_compact,
        }
    )
