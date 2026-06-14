# Phase 0 Research: CLI Host

Seam signatures grounded in `loopplane.host`; decisions re-derived for LoopPlane.

## R1 — The host seam the CLI drives

- `LoopPlaneHost(config: RuntimeConfig, *, working_scope)` — build once, run many.
- `await host.run(prompt, on_event, *, on_approval, working_scope) -> RunOutcome` —
  the one-shot run; `on_event: EventSink` receives every normalized event in order;
  `RunOutcome` carries `termination_reason`, `turns_taken`, and a history snapshot.
- `host.session(on_event, ...)` — async context manager for an interactive round-trip.
- `host.list_sessions() -> list[SessionSummary]`, `await host.resume(session_id)`.

**Decision**: `run` is built on `host.run`; `chat` repeatedly calls `host.run` per
user turn (each turn is one run over the shared host, which already isolates
sequential runs — FR-006 of unit 002); `sessions` uses `list_sessions`/`resume`.
The CLI adds nothing to the host and re-implements no runtime internal (FR-008).

## R2 — Rendering from the normalized event stream

`EventSink = Callable[[RuntimeEvent], Awaitable[None]]`. **Decision**: the renderer is
an `EventSink` that writes to an injected text stream, matching event types:
assistant-output-increment → the text; tool-call-started/-completed → a metadata-safe
marker (tool name + outcome, never raw I/O); run-terminated → the outcome line. It
prints only public-safe metadata and assistant text (FR-004/FR-009), so the renderer
is unit-testable by capturing a `StringIO`.

## R3 — The console entry point

**Decision**: add `[project.scripts] loopplane = "loopplane.cli:main"`. `main()` is a
synchronous wrapper: it parses args (`argparse`), dispatches to a command, and runs
the async command via `anyio.run`. This is additive — installing the package without
running `loopplane` changes nothing (FR-010/SC-005), and `argparse` adds no
dependency.

## R4 — Credential-free default + provider selection (FR-005/FR-006)

The built-in **scripted demo model** is the default: it runs with no credential and
no network, so `chat`/`run` work offline and are fully testable. **Decision**:
`select_model(env)` returns the scripted demo unless the environment names an
importable `ModelBoundary` builder (e.g. `LOOPPLANE_MODEL=module:function`) — then it
imports and calls it. The selection never prints or partially echoes a credential
(FR-006/FR-009). The concrete network provider (Anthropic, etc.) is **out of scope**:
a user plugs one behind this seam, validated manually like unit 001's real-model
procedure. The selection logic is testable (no env → scripted; a fake builder → that
model).

## R5 — Testable core, thin REPL

**Decision**: the command dispatch (`app`), one-shot run (`session.run_once`), the
renderer, and provider selection are pure/injectable (model + input lines + output
stream are parameters), so the whole CLI is tested with a scripted model and captured
streams. The interactive REPL is a thin wrapper that reads real stdin and feeds the
same `run_once`. Ctrl-C / EOF end cleanly (FR-011): the REPL catches `KeyboardInterrupt`
/ `EOFError` and exits without a traceback.

## R6 — Exit codes and public-safe errors (FR-009/FR-012)

`run` exits 0 on success and non-zero on a usage error or an unrecoverable run; a
missing prompt prints a public-safe usage message. Errors are rendered as public-safe
messages — never a raw exception, private path, or credential. `--help` is provided by
`argparse`.

## R7 — Additive packaging (FR-010)

The only packaging change is the `[project.scripts]` entry; the wheel still ships
`py.typed` and every subpackage. The CLI introduces no new runtime dependency; a real
provider is an optional extra. The unit-014 packaging contract stays green.
