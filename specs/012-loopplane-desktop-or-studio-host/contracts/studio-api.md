# Contract: Desktop / Studio Host console & sidecar

The local surface of `loopplane.studio`. `StudioHost` is an **async context manager** over an embedded
`LoopPlaneHost`; a UI shell or terminal renders its view models. Every command is in-process; nothing
is networked or spawned.

## Lifecycle

```text
async with StudioHost(host) as studio:        # owns an anyio task group + session registry
    result = await studio.run("...")          # one-shot run
    ...
# exit: open sessions are closed, the task group is joined
```

`StudioHost(host: LoopPlaneHost)` — wrap an embedded host. The `async with` owns the task group that
holds interactive sessions open.

## Commands → view models

| Command | Behavior | Result |
|---|---|---|
| `await studio.run(prompt)` | Drive one run through `host.run` (with a discard sink). | `RunResultView`; a concurrent run → `ErrorView(kind="conflict")`; an empty prompt → `ErrorView(kind="invalid")` (FR-001–FR-003). |
| `await studio.open_session()` | Enter `host.session(...)` in the task group; register by id. | `session_id: str`; a second open while active → `ErrorView(kind="conflict")` (FR-010, FR-003). |
| `studio.list_sessions()` | `host.list_sessions()`. | `tuple[SessionSummaryView, ...]` (FR-010). |
| `studio.select(session_id)` | Registry lookup. | the live entry, or `ErrorView(kind="not-found")` (FR-011). |
| `await studio.submit(session_id, prompt)` | `Session.submit(prompt)`. | `OutcomeView`; unknown id → `ErrorView(not-found)` (FR-020). |
| `studio.answer_approval(session_id, request_id, *, allow, scope="once", reason=None)` | `Session.answer_approval(...)`. | `bool` (false if unknown request id); unknown session → `ErrorView(not-found)` (FR-021). |
| `studio.answer_question(session_id, request_id, answers)` | `Session.answer_question(...)`. | `bool`; unknown session → `ErrorView(not-found)` (FR-021). |
| `await studio.cancel(session_id)` | `Session.cancel()` + close the entry. | `None`; unknown id → `ErrorView(not-found)`. Never hangs (FR-022). |
| `studio.history_view(session_id)` | `host.history_snapshot(session_id)`. | `tuple[HistoryEntryView, ...]` (metadata-only); unknown → `ErrorView(not-found)` (FR-030). |

For the interactive approval round-trip a developer may either inject an `on_approval` handler when
opening the session, or answer out-of-band via `answer_approval` (FR-021) — both in-process.

## View models (metadata-only)

See [data-model.md](../data-model.md). `RunResultView` / `OutcomeView` (session_id, termination_reason,
turns_taken, `history` of `{role, block_count}`, consumer_failures); `SessionSummaryView`
(session_id, label); `ErrorView` (kind, detail). **No view carries conversation content, tool I/O, or a
secret** (FR-030, FR-050, NFR-006).

## Sidecar lifecycle

```text
sidecar = InProcessSidecar(host)
await sidecar.start()
result = await sidecar.studio.run("...")
await sidecar.stop()      # idempotent
await sidecar.stop()      # no-op
```

| Behavior | Requirement |
|---|---|
| `start()` makes the studio available; the console reaches the host only through the sidecar | FR-040 |
| `stop()` is idempotent and leaves no orphaned run | FR-041, SC-006 |
| A command after `stop()` → `ErrorView(kind="not-available")` | FR-041, SC-004 |
| Spawning a real OS process is **reserved** | (out of scope) |

## Cross-cutting guarantees

| Guarantee | Requirement |
|---|---|
| Views are metadata-only (no history blocks / tool I/O) | FR-030, NFR-006, SC-003 |
| Command → view is deterministic | NFR-004, SC-002 |
| Cancelled session / idempotent stop never hang or orphan | FR-022, FR-041, SC-006 |
| No network egress; no OS process spawned | FR-051, NFR-006 |
| No tool executed by this layer; live bus never re-emitted | NFR-002, NFR-003, SC-005 |
