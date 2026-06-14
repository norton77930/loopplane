# Data Model: Desktop / Studio Host

All structures are **public-safe** and, for view models, **metadata-only**. They are the layer's own
edge types; they wrap — never replace — the public host types. View models are plain frozen
dataclasses (no serialization framework — the studio is in-process).

## View models (console → developer) — metadata-only

### `HistoryEntryView`
| Field | Type | Source | Notes |
|---|---|---|---|
| `role` | `str` | `HistoryEntry.role` | Metadata. |
| `block_count` | `int` | `len(HistoryEntry.blocks)` | **Count only** — the raw blocks (content) are never surfaced (FR-030, NFR-006). |

### `RunResultView` / `OutcomeView` — the projection of `RunOutcome`
| Field | Type | Source |
|---|---|---|
| `session_id` | `str` | `RunOutcome.session_id` |
| `termination_reason` | `str` | `RunOutcome.termination_reason` |
| `turns_taken` | `int` | `RunOutcome.turns_taken` |
| `history` | `tuple[HistoryEntryView, ...]` | projected `RunOutcome.history` |
| `consumer_failures` | `tuple[str, ...]` | `RunOutcome.consumer_failures` |

(`RunResultView` for a one-shot `run`; `OutcomeView` for an interactive `submit` — same shape.)

### `SessionSummaryView` — the projection of the host's `SessionSummary`
| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | Public id. |
| `label` | `str \| None` | Host-set label; metadata. Read via a structural protocol (the host does not export `SessionSummary`). |

### `ErrorView` — the one public-safe error/conflict/not-found envelope
| Field | Type | Notes |
|---|---|---|
| `kind` | `"invalid" \| "conflict" \| "not-found" \| "not-available"` | The failure class. |
| `detail` | `str` | A fixed public-safe message — never a stack trace, internal type, path, or secret (FR-050, SC-003). |

## Console commands (developer → console)

Commands are the `StudioHost` methods (a structured command surface a UI shell drives). Each returns a
view model or raises nothing the caller cannot handle — failures are returned as an `ErrorView`.

| Command (method) | Maps to | Returns |
|---|---|---|
| `run(prompt)` | `host.run(prompt, discard_sink)` | `RunResultView` or `ErrorView(conflict/invalid)` |
| `open_session()` | enter `host.session(...)` in the task group | `session_id: str` or `ErrorView(conflict)` |
| `list_sessions()` | `host.list_sessions()` | `tuple[SessionSummaryView, ...]` |
| `select(session_id)` | registry lookup | the entry, or `ErrorView(not-found)` |
| `submit(session_id, prompt)` | `Session.submit(prompt)` | `OutcomeView` or `ErrorView(not-found)` |
| `answer_approval(session_id, request_id, *, allow, scope, reason)` | `Session.answer_approval(...)` | `bool` (false if unknown id) or `ErrorView(not-found)` |
| `answer_question(session_id, request_id, answers)` | `Session.answer_question(...)` | `bool` or `ErrorView(not-found)` |
| `cancel(session_id)` | `Session.cancel()` + close | `ErrorView(not-found)` if unknown |
| `history_view(session_id)` | `host.history_snapshot(session_id)` | `tuple[HistoryEntryView, ...]` or `ErrorView(not-found)` |

## Internal seams (not surfaced)

### `SessionEntry` / session registry — `sessions.py`
A lifespan-scoped mapping `session_id → SessionEntry`. A `SessionEntry` holds the live Phase-2
`Session` handle and a `close` event. Created on open, removed on close/cancel. Honors the host's
sequential-per-instance guarantee (at most one active; otherwise a conflict view).

### `_discard` sink — `console.py`
`async def _discard(event: object) -> None: return None` — passed as `host.run`'s `on_event`. Typed
`object` (a valid `EventSink` by contravariance) so the layer names no event type and imports no
`loopplane.events` (boundary discipline).

## Sidecar contract — `sidecar.py`

### `SidecarHost` (Protocol)
```text
class SidecarHost(Protocol):
    @property
    def studio(self) -> StudioHost: ...   # the console over the embedded host
    async def start(self) -> None: ...
    async def stop(self) -> None: ...      # idempotent
```

### `InProcessSidecar`
Wraps a `LoopPlaneHost` + a `StudioHost`; `start` makes the studio available, `stop` idempotently tears
down the studio's task group (no orphaned run). A command after `stop` returns an `ErrorView(
not-available)`. Spawning a real OS process is reserved.

## Determinism & safety invariants

- **Metadata-only views**: no view carries a `ContentBlock`, tool I/O, or secret; history is counts +
  roles only (FR-030, NFR-006, SC-003).
- **Deterministic**: a command's view is a pure function of the command + the host's outputs; the same
  command sequence over the same scripted host yields the same views (NFR-004, SC-002).
- **Fail-safe**: every miss/unknown id → an explicit `ErrorView`/`False`; every raising injected handler
  is contained; a concurrent run → a conflict view; a stopped sidecar → a not-available view (NFR-005,
  SC-004/006).
