# Contract: `loopplane.commands` and the remote client's server dependencies (unit 079)

## Part 1 — `loopplane.commands` public API

### Before 079

```python
__all__ = ["CommandResult", "CommandContext", "CommandRegistry", "default_registry"]
```

### After 079

```python
__all__ = [
    "CommandResult",
    "CommandContext",
    "CommandDescriptor",   # new
    "CommandRegistry",
    "default_registry",
]
```

### `CommandRegistry` — changed members

```python
def register(
    self,
    name: str,
    handler: _Handler,
    *,
    summary: str = "",
    remote_safe: bool = True,
) -> None: ...
```

Additive keyword-only parameters with defaults; every existing two-argument call site keeps
compiling and keeps its behavior.

```python
@property
def names(self) -> tuple[str, ...]: ...        # unchanged

def describe(self) -> tuple[CommandDescriptor, ...]: ...   # new

def is_command(self, line: str) -> bool: ...   # unchanged

def dispatch(self, line: str, ctx: CommandContext) -> CommandResult: ...
```

`dispatch` gains one branch, evaluated after the handler is resolved and before it is
called: if `ctx.remote` is true and the command's `remote_safe` is false, return
`CommandResult(kind="error", text=f"/{name}: not available over a remote connection")`.
All other paths — unknown command, handler raised, normal success — are unchanged.

### Invariants preserved

- `dispatch` never raises (the bare `except Exception` stays).
- No command reaches the Tool Gateway or the Event Bus.
- No new `CommandResult.kind` value.
- No event, no `SCHEMA_VERSION` bump, no checkpoint record change.
- With `ctx.remote` left at its default `False` and `remote_safe` left at its default
  `True`, dispatch is byte-identical to the pre-079 implementation.

### Consumers that must keep working unchanged

| Consumer | Location | Change required |
| --- | --- | --- |
| CLI REPL | `src/loopplane/cli/session.py` | passes `remote=False` explicitly on the local path; gains the remote path |
| Web/API host | `src/loopplane/webapi/app.py` `POST /v1/commands` | none |
| Desktop sidecar | `apps/desktop/sidecar/methods/command.py` | none — one `command.execute` method dispatches any line, so the six-registry discipline is not triggered |

## Part 2 — server endpoints the remote client consumes

The client depends on these; this unit changes **none** of them. Listed so a future change
to any of them is visibly a change to this unit's assumptions.

| Operation | Request | Response |
| --- | --- | --- |
| open a conversation | `POST /v1/sessions` (optional `model` query) | `{"session_id": str}` |
| send a turn | `POST /v1/sessions/{id}/submit` with `{"prompt": str, ...}` | `RunResult` (metadata only) |
| answer an approval | `POST /v1/sessions/{id}/approvals/{request_id}` with `{"allow": bool, "scope": "once"\|"session", "reason": str\|null}` | `{"resolved": bool}` |
| answer a question | `POST /v1/sessions/{id}/questions/{request_id}` with `{"answers": [str]}` | `{"resolved": bool}` |
| interrupt | `POST /v1/sessions/{id}/cancel` | `{"resolved": true}` — **also ends the live session server-side** |
| stream events | `GET /v1/sessions/{id}/events`, optional `Last-Event-ID` header | `text/event-stream` |
| list conversations | `GET /v1/sessions` | `SessionSummaryView[]`, already filtered to the caller |
| run a command | `POST /v1/commands` with `{"command": str, "session_id": str\|null}` | `{"kind": str, "text": str}` |

Authentication: a bearer credential on every request, resolved by the server's configured
authenticator. Ownership and non-disclosure are enforced server-side; a session the caller
does not own answers `404` without revealing whether it exists.

### SSE frame shape the client parses

```
id: <sequence>\n
data: <serialized runtime event JSON>\n
\n
```

The `id:` line is present when the server has a replay buffer or a replay store configured
and absent otherwise. The client:

1. splits frames on a blank line,
2. reads `id:` when present and records it as the stream cursor,
3. passes the `data:` payload to `deserialize_event`,
4. drops the frame if deserialization yields `None` (unknown or corrupt event),
5. drops the frame if its sequence is at or below the cursor,
6. otherwise renders it through the same `EventRenderer` the local path uses.

### Reconnection

On a dropped stream the client re-issues `GET /v1/sessions/{id}/events` with
`Last-Event-ID: <cursor>`. The server merges its retained buffer, its queued live frames,
and any durable replay records in sequence order; the client's cursor check removes anything
it has already rendered. Attempts are bounded; on exhaustion the client reports and returns
control to the operator.

A `404` on reconnect means the conversation is no longer resumable on that server (it ended,
or the worker holds no live entry and no durable replay store is configured). The client
reports that in public-safe terms and exits the conversation.
