# Phase 1 Data Model: CLI and Remote Parity (079)

Only two packages gain shapes: `loopplane.commands` (a classification and a description) and
`loopplane.cli` (the remote connection's client-side state). Nothing here is persisted, and
nothing crosses the wire in a new form.

## 1. `loopplane.commands` — command surface

### `CommandDescriptor` (new, public)

A public-safe description of one command, returned by the registry so a host can render a
listing.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `str` | lower-case, without the leading `/` |
| `summary` | `str` | one line, public-safe, no host configuration detail |
| `remote_safe` | `bool` | whether the command may run over a remote connection |

Frozen dataclass. Ordering when enumerated: by `name`, matching the existing
`CommandRegistry.names` contract.

### `_CommandSpec` (new, internal)

What the registry stores per command: the handler plus its `summary` and `remote_safe`.
Internal because handlers are internal; `CommandDescriptor` is its public projection.

### `CommandContext` (extended)

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `host` | `_CommandHost` | — | unchanged |
| `principal_id` | `str` | — | unchanged |
| `session_id` | `str \| None` | `None` | unchanged |
| `models` | `tuple[str, ...]` | `()` | unchanged |
| `args` | `str` | `""` | unchanged |
| **`remote`** | `bool` | **`False`** | **new** — the caller reached this surface over a remote connection |

`remote=False` by default, so every existing construction site (CLI REPL, `POST /v1/commands`,
the Desktop sidecar) keeps byte-identical behavior (invariant G5).

### `_CommandHost` (extended protocol)

Existing seams: `session_cost`, `monthly_spend`, `inspect_memory`, `compact_session`.

New seams, all synchronous public `LoopPlaneHost` methods that already exist:

| Seam | Used by | Returns |
| --- | --- | --- |
| `list_sessions()` | `/sessions` | session summaries (filtered to the caller's principal by the handler) |
| `agent_controls(session_id)` | `/permission` | the owner-scoped posture projection (077) |
| `history_snapshot(session_id)` | `/history` | history entries, projected to role + block count only |

A handler must stay synchronous: `_Handler` is `Callable[[CommandContext], CommandResult]`
and dispatch is synchronous. Any capability whose host seam is a coroutine cannot become a
command in this unit.

### Built-in command set after this unit

| Command | Reads | `remote_safe` | Notes |
| --- | --- | --- | --- |
| `/cost` | `session_cost`, `monthly_spend` | `True` | unchanged |
| `/model` | `ctx.models` | `True` | unchanged |
| `/memory` | `inspect_memory` | `True` | unchanged |
| `/compact` | `compact_session` | **`False`** | the only mutator; irreversible and unverifiable from a remote view (research R9) |
| `/help` | the registry itself | `True` | new — lists the commands available in the current context |
| `/sessions` | `list_sessions` | `True` | new — the caller's own conversations, metadata only |
| `/permission` | `agent_controls` | `True` | new — current permission and plan posture, no rule expressions |
| `/history` | `history_snapshot` | `True` | new — role + block count per entry, never block content |

### Dispatch outcomes

`CommandResult.kind` keeps its existing three values; no new value is introduced.

| Situation | `kind` | Text shape |
| --- | --- | --- |
| handler succeeded | `ok` | the handler's public-safe text |
| unknown command | `unknown` | `unknown command: /x` (unchanged) |
| handler raised | `error` | `/x: command failed` (unchanged) |
| **remote context, `remote_safe=False`** | `error` | `/x: not available over a remote connection` |
| session-scoped command with no session | `error` | existing per-command text |

The remote refusal is evaluated **before** the handler runs, so a refused command touches no
host seam.

## 2. `loopplane.cli` — remote connection state

None of this is persisted; it lives for the duration of one `loopplane remote` invocation.

### `RemoteEndpoint` (new, internal to the CLI)

| Field | Type | Notes |
| --- | --- | --- |
| `base_url` | `str` | the server root; the `/v1` prefix is appended by the client |
| `token` | `str` | held only in memory, never rendered, never logged, never included in an error |
| `session_id` | `str \| None` | set once a conversation is opened or attached |

Validation: a blank or missing `base_url` is a usage error; a missing token is a usage error
reported without echoing the value that was supplied.

### `StreamCursor` (new, internal to the CLI)

| Field | Type | Notes |
| --- | --- | --- |
| `last_sequence` | `int \| None` | the highest `id:` rendered; sent back as `Last-Event-ID` |
| `attempts` | `int` | reconnection attempts used since the last successful frame |

Rules:
- `last_sequence` advances only when a frame is actually rendered, so a reconnect never
  skips an unrendered frame.
- A frame whose sequence is `<= last_sequence` is dropped without rendering (the client half
  of the no-loss guarantee; the server half is `reconnect_stream`).
- `attempts` resets to `0` on any successfully received frame and caps the retry loop.

### Terminal interaction state

The interactive loop (local and remote) tracks only:

- the open conversation's identity,
- the pending approval request id, if any,
- the pending question request id and its option list, if any.

Each is cleared when resolved. There is no other client-side state; everything else is read
from the event stream or from the host.
