# Phase 0 Research: CLI and Remote Parity (079)

All findings below were read from source in this repository. Line references are to the
state of the tree at the time of planning.

## R1 — The interactive seam the CLI never used

**Decision**: rebuild the interactive terminal loop on `LoopPlaneHost.session()` instead of
`LoopPlaneHost.run()`.

**Rationale**: `LoopPlaneHost.run()` calls `controller.create_session(...)` on every
invocation (`src/loopplane/host/host.py:182-186`), so the CLI's `chat_loop` — which calls
`run_once` per line (`src/loopplane/cli/session.py:53`) — starts a fresh conversation each
turn. `LoopPlaneHost.session()` (`host.py:249-286`) opens one conversation and yields a
`Session` (`host.py:934-1010`) with `submit()`, `cancel()`, `answer_approval()`,
`answer_question()`, and `aclose()`. Every US1–US3 capability is already present behind that
handle; the gap is entirely in the CLI's wiring.

**Alternatives considered**: adding a `session_id` parameter to `host.run()` — rejected: it
changes a public signature and duplicates what `session()` already provides.

## R2 — Cancellation is re-armed, so a conversation survives an interrupt

**Decision**: implement US3 as `Session.cancel()` per turn, keeping the conversation open.

**Rationale**: `RuntimeController.cancel()` sets a one-shot event
(`src/loopplane/controller/controller.py:1045-1049`) that takes effect "pre-turn and
mid-stream", and `drive()`'s `finally` re-arms it — "The signal is one-shot; arm a fresh one
for the next run" (`controller.py:688-689`). A cancelled turn therefore leaves the session
usable for the next `submit()`. `Session.cancel()` additionally calls
`on_reviewer_disconnect` (`host.py:973-977`), which denies pending approvals and cancels
pending questions (`src/loopplane/approval/interactions.py:58-74`), satisfying FR-008's
"nothing left waiting" both on exit and on interrupt.

**Alternatives considered**: a per-turn task group cancelled from a signal handler —
rejected: it duplicates a cancellation path the runtime already owns and would need
platform-specific signal handling.

## R3 — Approvals arrive through a relay inside the event sink

**Decision**: answer approvals from the same input source the REPL reads turns from.

**Rationale**: `host._bind` wraps a host-supplied `on_approval` in a `relay` coroutine
awaited from inside the run sink (`host.py:896-931`), and a raising handler is contained —
it denies and lets the run continue. So the CLI's approval handler runs *while a turn is in
flight*. Reading the answer from the same line source the REPL already consumes keeps one
input abstraction and keeps the whole loop testable with a list of strings, exactly as
`chat_loop(host, lines, out)` is testable today. `ApprovalRequestedPayload` carries
`request_id`, `call_id`, `tool_name`, `input_summary`
(`src/loopplane/events/envelope.py:116-121`) — `tool_name` plus `input_summary` is the
public-safe decision summary FR-005 requires, with no raw tool I/O.

**Alternatives considered**: a separate prompt channel or a second thread for approvals —
rejected: it would fork the input abstraction and break the list-driven tests.

## R4 — Questions are answered off the event stream, not through a callback

**Decision**: render `QuestionAskedEvent` in the renderer and answer it via
`Session.answer_question(request_id, answers)`.

**Rationale**: there is no `on_question` counterpart to `on_approval`; questions surface as
`QuestionAskedEvent` with `request_id` and a list of `Question{text, options}`
(`envelope.py:140-152`), and are resolved by `Session.answer_question`
(`host.py:1004-1005`). The renderer is already the component that sees every event, so the
interactive loop reads the pending question from the stream and prompts for it.

## R5 — The web/API host already exposes everything the remote client needs

**Decision**: the remote bridge is an HTTP + SSE client of the existing endpoints under the
default `/v1` prefix (`src/loopplane/webapi/app.py:155,310`). No endpoint, field, or
streaming contract changes.

**Rationale**: the required operations all exist —
`POST /v1/sessions` → `OpenedSession{session_id}` (`app.py:438-461`);
`POST /v1/sessions/{id}/submit` with a `RunRequest` → `RunResult` (`app.py:656-683`);
`POST /v1/sessions/{id}/approvals/{request_id}` with `SessionAnswer{allow, scope, reason}`
→ `Resolved` (`app.py:685-696`);
`POST /v1/sessions/{id}/questions/{request_id}` with `QuestionAnswer{answers}` → `Resolved`
(`app.py:698-707`);
`POST /v1/sessions/{id}/cancel` → `Resolved` (`app.py:709-716`);
`GET /v1/sessions/{id}/events` as SSE honouring `Last-Event-ID` (`app.py:463-507`);
`GET /v1/sessions` → owner-filtered `SessionSummaryView[]` (`app.py:720-728`);
`POST /v1/commands` with `CommandRequest{command, session_id}` → `CommandResultView`
(`app.py:872-892`).
Ownership is enforced server-side by `_require`/`_owned_or_404`, both of which answer 404
without revealing whether another principal's session exists (`app.py:312-333`) — FR-029 is
satisfied by the server as it stands.

**Alternatives considered**: the WebSocket live channel (`app.py:523-654`) — rejected as the
primary path: it needs a ticket round-trip (`app.py:509-521`) and adds a second framing to
parse, while its `abort` handling is identical to the cancel endpoint's (`app.py:609-615`).
SSE plus small POSTs covers every requirement with one transport.

## R6 — Remote events can reuse the local renderer verbatim

**Decision**: parse each SSE frame's `data:` payload with `deserialize_event` and feed the
result to the same `EventRenderer` the local path uses.

**Rationale**: session frames are `id: {sequence}\ndata: {serialize_event(event)}\n\n` when
a replay buffer or replay store is configured, and `data: {...}\n\n` otherwise
(`src/loopplane/webapi/sessions.py:189-209`). `deserialize_event` already exists and is
total — unknown types and corrupt input yield `None` rather than raising
(`src/loopplane/events/serde.py:21-33`). Reusing the renderer means remote output is
public-safe by construction (FR-026) with no second rendering implementation to keep in
sync.

## R7 — Reconnection reuses the server's no-loss merge

**Decision**: track the last `id:` seen and send it back as the `Last-Event-ID` header on
reconnect; bound the attempts.

**Rationale**: `reconnect_stream` merges the retained ring buffer, the frames already queued
live, and any durable replay records, keyed by sequence, and emits them in order before
continuing live (`src/loopplane/webapi/sessions.py:62-126`). The no-loss guarantee is
therefore the server's; the client's obligation is only to remember the last sequence it
rendered and to not re-render anything at or below it. `frame_sequence` (`sessions.py:47-59`)
documents the exact `id:` parsing rule the client mirrors.

**Note on the server's own limit**: when a session is not live on the serving worker and no
durable replay store is configured, the events endpoint answers 404 (`app.py:473-478`).
That is the concrete shape of FR-036's "no longer resumable" case.

## R8 — Remote interrupt ends the live session (spec correction required)

**Finding**: `POST /v1/sessions/{id}/cancel` calls `entry.session.cancel()` **and**
`entry.close.set()` (`app.py:709-716`); the WebSocket `abort` message does exactly the same
(`app.py:609-615`). Server-side, interrupting a remote turn therefore tears the live session
down — it does not return it to an idle-but-open state the way a local `Session.cancel()`
does.

**Decision**: keep the server untouched and correct the specification instead. FR-028 is
restated as: the operator can interrupt a running remote turn; the terminal reports that
interruption ends the live remote connection; the conversation remains listed and its
history remains available afterwards. The terminal returns to its prompt, and the operator
may open a new remote conversation.

**Rationale**: changing the cancel endpoint's semantics is an outward-contract change, which
is a human approval gate and is explicitly out of scope for this unit. The local and remote
interrupt semantics differ because the local host owns the session object while the remote
one owns only a connection to it; stating that difference honestly is better than hiding it
behind a client-side reconnect that would silently start a *different* conversation.

**Alternatives considered**: transparently re-opening a session after a remote interrupt —
rejected: the new session would have a different identity and an empty history, which is
precisely the "new conversation per turn" defect US1 exists to remove.

## R9 — Command policy is enforced client-side, by design

**Decision**: the remote-safety classification lives on the shared command surface, and the
terminal refuses a non-remote-safe command before it is sent.

**Rationale**: the spec's Out of Scope excludes new server-side command policy enforcement.
`POST /v1/commands` dispatches against the server's own registry (`app.py:872-892`), so a
client-side refusal is the only enforcement point that does not change the server. The
classification still belongs to `loopplane.commands` rather than to the CLI, so all three
consuming hosts read one definition (FR-019).

**Which command is not remote-safe**: `/compact`. It is the only mutating command
(`src/loopplane/commands/__init__.py:14-15,101-110`), it rewrites conversation history
irreversibly, and its effect is invisible to a remote operator because history is projected
as metadata only (`HistoryEntryView` is `{role, block_count}`,
`src/loopplane/webapi/models.py:190-196`). Refusing exactly the irreversible, unverifiable
operation over a remote link is the substance of a "remote-safe command policy". Every other
command is read-only and remains available remotely.

**Compatibility**: `remote_safe` defaults to `True` and `CommandContext.remote` defaults to
`False`, so the CLI REPL, `POST /v1/commands`, and the Desktop sidecar keep byte-identical
behavior for the four existing commands (FR-020, invariant G5).

## R10 — New commands need no new sidecar RPC method

**Decision**: add commands to the registry only; do not touch the Desktop sidecar's method
registry.

**Rationale**: the sidecar exposes a single `command.execute` method that dispatches any
line against the shared registry with a real `LoopPlaneHost`
(`apps/desktop/sidecar/methods/command.py:103-146`). New commands therefore reach the
desktop composer with no change to `_DESKTOP_METHOD_NAMES` and no six-registry edit. The
`_CommandHost` protocol gains three synchronous public host seams —
`list_sessions()`, `agent_controls()`, `history_snapshot()` (`host.py:288-292`, `:509`,
`:441`) — all of which the real host already implements on all three surfaces.

**Constraint this imposes**: every new command handler must be synchronous, because
`_Handler` is `Callable[[CommandContext], CommandResult]`
(`src/loopplane/commands/__init__.py:64`) and dispatch is synchronous. This rules out a
`/resume` command (the host's `resume` is a coroutine, `host.py:294`); resuming stays a CLI
subcommand.

## R11 — The HTTP dependency is already declared

**Decision**: import `httpx` lazily inside the remote module, guarded by
`try/except ImportError`, and reuse the existing `net` extra.

**Rationale**: `pyproject.toml:39` already declares `net = ["httpx>=0.27"]`, and `httpx` is
in the dev dependency group (`pyproject.toml:64`), so tests can exercise the remote path.
Lazy import is sanctioned guard pattern ① of invariant G4. No new dependency and no new
extra means no §E approval gate, and the terminal host still imports and runs with only the
base dependencies installed (FR-030).

**Alternatives considered**: `urllib` from the standard library — rejected: it would mean
hand-rolling SSE reading and connection handling that `httpx` provides, for no benefit,
since the dependency is already declared.

## R12 — Testing approach

**Decision**: drive the local paths with the existing list-of-lines core, and drive the
remote paths against the real application via `httpx`'s ASGI transport.

**Rationale**: the CLI's testable core already takes `(host, lines, out)`
(`src/loopplane/cli/session.py:28`), and the existing suites
`tests/integration/test_cli_us1.py`–`us5.py` use it. For remote coverage, `httpx.ASGITransport`
lets the client talk to a real `create_app(...)` in-process, so the tests exercise the actual
endpoints, the actual SSE framing, and the actual ownership rules rather than a mock.

**Known hazard**: an in-process client reading an endless SSE stream can hang. The session
event stream ends when the session closes, so tests must close the session (or cancel) to
terminate the stream, and the suite's 60-second per-test timeout
(`pyproject.toml:97-101`) is the backstop.

**Public-safety fixtures**: poison values come from `tests/helpers/public_safety.py`'s
synthetic markers; no hand-written realistic private path, host name, or address appears in
a fixture.
