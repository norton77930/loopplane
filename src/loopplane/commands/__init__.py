"""Backend-semantic slash commands (spec 065; gap G14; extended by spec 079).

A small host command surface: a :class:`CommandRegistry` parses a leading-``/``
command and dispatches to a handler that maps to an EXISTING host seam -- ``/cost``
(064 ``session_cost``/``monthly_spend``), ``/model`` (the wiring-supplied model
list), ``/memory`` (``inspect_memory``), ``/compact`` (``compact_session``, the
loop's ``compact_history``), and — added by 079 — ``/help`` (the registry itself),
``/sessions`` (``list_sessions``), ``/permission`` (``agent_controls``), and
``/history`` (``history_snapshot``).

Commands are a host **UX**, NOT tools: each handler calls an existing host method,
so a command never reaches the Tool Gateway (V) or the Event Bus (VI), adds no new
event/``TerminationReason``, and bumps no ``SCHEMA_VERSION``. The same registry is
shared by the CLI chat REPL, the web/API ``POST /commands`` endpoint, and the
Desktop sidecar's ``command.execute`` (ADR 0017). Dispatch never raises (an unknown
command / a failing seam -> a normalized result) and is public-safe (no
DSN/secret/another-principal's data). Only ``/compact`` mutates, and it reuses the
loop's compaction seam.

**Remote safety** (079): every command carries a ``remote_safe`` classification,
and a context can declare that its caller reached the surface over a remote
connection. A command that is not remote-safe is refused there *before* its
handler runs, so it touches no host seam. ``/compact`` is the one built-in that is
not remote-safe: it is the only mutator, it rewrites conversation history
irreversibly, and its effect is invisible to a remote operator, since history
crosses the wire as metadata only. Both new knobs default to the pre-079 behavior
(``remote_safe=True``, ``CommandContext.remote=False``), so every existing consumer
is byte-identical.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, Protocol

__all__ = [
    "CommandResult",
    "CommandContext",
    "CommandDescriptor",
    "CommandRegistry",
    "default_registry",
    "format_command_listing",
]

REMOTE_REFUSAL = "not available over a remote connection"
"""Why a non-remote-safe command was refused; carries no host-private detail."""


@dataclass(frozen=True)
class CommandResult:
    """A normalized, host-renderable command result (public-safe)."""

    kind: Literal["ok", "unknown", "error"]
    text: str


@dataclass(frozen=True)
class CommandDescriptor:
    """What a host may tell an operator — or ask — about one command (079).

    ``session_scoped`` exists for the hosts that have principals: it tells them
    which commands read a specific conversation and therefore need an ownership
    check before dispatch. It is declared here, beside the command, precisely so
    that adding a command cannot silently skip a host's gate — which is exactly
    how unit 079 first introduced a cross-principal disclosure.
    """

    name: str
    summary: str
    remote_safe: bool
    session_scoped: bool = False


class _CommandHost(Protocol):
    """The existing host seams a command may read (064 + inspection + 065 + 079).

    Deliberately structural and loosely typed: the registry describes what it
    reads without importing a host type, and each handler projects only
    public-safe fields out of whatever the host returns.
    """

    def session_cost(self, session_id: str) -> Decimal | None: ...

    def monthly_spend(self, principal_id: str) -> Decimal | None: ...

    def inspect_memory(self, query: str | None = ...) -> Sequence[object]: ...

    def compact_session(self, session_id: str) -> bool: ...

    def list_sessions(self) -> Sequence[object]: ...

    def agent_controls(self, session_id: str) -> object: ...

    def history_snapshot(self, session_id: str) -> Sequence[object]: ...


@dataclass(frozen=True)
class CommandContext:
    """What a handler needs; built by each host's wiring (CLI / web-API / sidecar)."""

    host: _CommandHost
    principal_id: str
    session_id: str | None = None
    models: tuple[str, ...] = ()
    args: str = ""
    # 079: whether the caller reached this surface over a remote connection.
    # False for every pre-079 construction site, keeping them byte-identical.
    remote: bool = False


_Handler = Callable[[CommandContext], CommandResult]


@dataclass(frozen=True)
class _CommandSpec:
    """What the registry stores per command.

    The callable field is named ``run`` rather than the obvious alternative: the
    Tool Gateway's structural audit (``tests/contract/test_tool_gateway.py``)
    refuses, anywhere outside the gateway, the literal text of a dotted call to
    a tool handler. A command handler has nothing to do with a tool handler, but
    that audit is worth more as a blunt, unbypassable string check than as one
    carrying an exception for this package — so the name gives way instead.
    """

    run: _Handler
    summary: str
    remote_safe: bool
    session_scoped: bool


def _readable_session(ctx: CommandContext) -> bool:
    """Whether this caller may read this conversation's metadata (079).

    This is the **second** layer. A host with principals gates ownership before
    dispatch ever runs — `webapi/app.py` does, using
    `CommandRegistry.session_scoped_names()`. This check exists so that a host
    which forgets that gate degrades to "not found" rather than leaking, which
    is the failure this unit shipped once and must not ship twice.

    A conversation whose principal is unset belongs to a host that has no
    principals at all (the terminal, the desktop sidecar), so it is readable
    there. On a host that does have principals, such a session is already
    refused by the authoritative gate before reaching here.
    """

    if ctx.session_id is None:
        return False
    for summary in ctx.host.list_sessions():
        if getattr(summary, "session_id", None) != ctx.session_id:
            continue
        owner = getattr(summary, "principal_id", None)
        return owner is None or owner == ctx.principal_id
    return False


def _fmt_usd(value: Decimal | None) -> str:
    return "not tracked" if value is None else str(value)


def _cmd_cost(ctx: CommandContext) -> CommandResult:
    lines: list[str] = []
    if ctx.session_id is not None:
        # Every session-scoped command carries the second ownership layer, not
        # just the two 079 added: a spend figure is another principal's data.
        if not _readable_session(ctx):
            return CommandResult(kind="error", text="session not found")
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
    # The one irreversible command is the last one that should be missing this.
    if not _readable_session(ctx):
        return CommandResult(kind="error", text="session not found")
    try:
        compacted = ctx.host.compact_session(ctx.session_id)
    except KeyError:
        return CommandResult(kind="error", text="session not found")
    return CommandResult(
        kind="ok", text="compacted" if compacted else "nothing to compact"
    )


def _cmd_sessions(ctx: CommandContext) -> CommandResult:
    """The caller's own conversations, metadata only (079)."""

    mine = [
        summary
        for summary in ctx.host.list_sessions()
        if getattr(summary, "principal_id", None) in (None, ctx.principal_id)
    ]
    if not mine:
        return CommandResult(kind="ok", text="no sessions")
    lines = []
    for summary in mine:
        session_id = getattr(summary, "session_id", "?")
        label = getattr(summary, "label", None)
        lines.append(f"- {session_id}" + (f"  {label}" if label else ""))
    return CommandResult(kind="ok", text="\n".join(lines))


def _cmd_permission(ctx: CommandContext) -> CommandResult:
    """The current permission and plan posture (079), never a rule expression."""

    if ctx.session_id is None:
        return CommandResult(kind="error", text="no active session")
    if not _readable_session(ctx):
        # Same answer for "not yours" and "does not exist" — never disclose which.
        return CommandResult(kind="error", text="session not found")
    try:
        projection = ctx.host.agent_controls(ctx.session_id)
    except KeyError:
        return CommandResult(kind="error", text="session not found")
    permission = getattr(projection, "permission", None)
    if permission is None:
        return CommandResult(kind="ok", text="permission posture: unavailable")
    default_mode = getattr(permission, "default_mode", None) or "(host default)"
    selectable = getattr(permission, "selectable_modes", ())
    modes = ", ".join(str(getattr(item, "id", "?")) for item in selectable) or "(none)"
    plan_available = bool(getattr(permission, "plan_entry_available", False))
    active = getattr(permission, "active_run", None)
    plan_active = bool(getattr(active, "plan_active", False)) if active else False
    return CommandResult(
        kind="ok",
        text=(
            f"mode: {default_mode}\n"
            f"selectable: {modes}\n"
            f"plan available: {'yes' if plan_available else 'no'}\n"
            f"plan active: {'yes' if plan_active else 'no'}"
        ),
    )


def _cmd_history(ctx: CommandContext) -> CommandResult:
    """Conversation shape only (079): a role and a block count per entry, never
    the block content."""

    if ctx.session_id is None:
        return CommandResult(kind="error", text="no active session")
    if not _readable_session(ctx):
        # Same answer for "not yours" and "does not exist" — never disclose which.
        return CommandResult(kind="error", text="session not found")
    try:
        entries = ctx.host.history_snapshot(ctx.session_id)
    except KeyError:
        return CommandResult(kind="error", text="session not found")
    if not entries:
        return CommandResult(kind="ok", text="no history")
    lines = []
    for entry in entries:
        role = getattr(entry, "role", "?")
        blocks = getattr(entry, "blocks", ())
        lines.append(f"- {role}: {len(blocks)} block(s)")
    return CommandResult(kind="ok", text="\n".join(lines))


class CommandRegistry:
    """A registry of slash commands; ``dispatch`` parses a leading-``/`` line,
    routes to a handler, and always returns a normalized result (never raises)."""

    def __init__(self, handlers: dict[str, _Handler] | None = None) -> None:
        self._specs: dict[str, _CommandSpec] = {
            name.lower(): _CommandSpec(
                run=handler, summary="", remote_safe=True, session_scoped=False
            )
            for name, handler in (handlers or {}).items()
        }

    def register(
        self,
        name: str,
        handler: _Handler,
        *,
        summary: str = "",
        remote_safe: bool = True,
        session_scoped: bool = False,
    ) -> None:
        """Register ``handler`` under ``name``.

        Every keyword is optional with a pre-079 default, so an existing
        two-argument call keeps its exact behavior.
        """

        self._specs[name.lower()] = _CommandSpec(
            run=handler,
            summary=summary,
            remote_safe=remote_safe,
            session_scoped=session_scoped,
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def describe(self) -> tuple[CommandDescriptor, ...]:
        """Every registered command, sorted by name (079)."""

        return tuple(
            CommandDescriptor(
                name=name,
                summary=spec.summary,
                remote_safe=spec.remote_safe,
                session_scoped=spec.session_scoped,
            )
            for name, spec in sorted(self._specs.items())
        )

    def session_scoped_names(self) -> frozenset[str]:
        """The commands that read one conversation and therefore need an
        ownership check from any host that has principals (079)."""

        return frozenset(
            name for name, spec in self._specs.items() if spec.session_scoped
        )

    def is_command(self, line: str) -> bool:
        return line.lstrip().startswith("/")

    def dispatch(self, line: str, ctx: CommandContext) -> CommandResult:
        text = line.strip()
        if not text.startswith("/"):
            return CommandResult(kind="unknown", text="not a command")
        name, _, args = text[1:].strip().partition(" ")
        spec = self._specs.get(name.lower())
        if spec is None:
            return CommandResult(kind="unknown", text=f"unknown command: /{name}")
        if ctx.remote and not spec.remote_safe:
            # Refused before the handler runs, so it touches no host seam (079).
            return CommandResult(kind="error", text=f"/{name}: {REMOTE_REFUSAL}")
        handler = spec.run
        try:
            return handler(replace(ctx, args=args.strip()))
        except Exception:
            # Fail-safe + public-safe: never crash, never leak -- a generic error.
            return CommandResult(kind="error", text=f"/{name}: command failed")


def format_command_listing(
    descriptors: Iterable[CommandDescriptor], *, remote: bool = False
) -> str:
    """The operator-facing command listing (079).

    Shared so that a host answering ``/help`` locally — the remote terminal does,
    because a listing produced on the server would describe the server's context
    and not the operator's — produces exactly the text the registry would.
    """

    listed = "\n".join(
        f"- /{descriptor.name}"
        + (f" — {descriptor.summary}" if descriptor.summary else "")
        for descriptor in descriptors
        if descriptor.remote_safe or not remote
    )
    return f"commands:\n{listed}"


def default_registry() -> CommandRegistry:
    """A registry with the built-in commands (065's four plus 079's four)."""

    registry = CommandRegistry()

    def _cmd_help(ctx: CommandContext) -> CommandResult:
        """List the commands usable where the caller is (079)."""

        return CommandResult(
            kind="ok",
            text=format_command_listing(registry.describe(), remote=ctx.remote),
        )

    # /compact is the one built-in that must not run remotely: the only mutator,
    # irreversible, and unverifiable from a remote view (spec 079 FR-021).
    registry.register(
        "compact",
        _cmd_compact,
        summary="compact this conversation",
        remote_safe=False,
        session_scoped=True,
    )
    registry.register(
        "cost", _cmd_cost, summary="session and monthly spend", session_scoped=True
    )
    registry.register("help", _cmd_help, summary="list available commands")
    registry.register(
        "history",
        _cmd_history,
        summary="this conversation's shape",
        session_scoped=True,
    )
    registry.register("memory", _cmd_memory, summary="search memory entries")
    registry.register("model", _cmd_model, summary="list available models")
    registry.register(
        "permission",
        _cmd_permission,
        summary="permission and plan posture",
        session_scoped=True,
    )
    registry.register("sessions", _cmd_sessions, summary="your conversations")
    return registry
