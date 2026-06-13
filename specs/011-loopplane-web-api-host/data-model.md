# Data Model: Web / API Host

All structures are **public-safe** and, for response bodies, **metadata-only**. They are the layer's
own transport-edge types; they wrap — never replace — the public host/event types. Request/response
bodies are `pydantic` models (validated, FR-016); internal seams are plain callables/dataclasses.

## Request models (client → host)

### `RunRequest`
| Field | Type | Notes |
|---|---|---|
| `prompt` | `str` | The run prompt. A plain string this phase; structured content blocks are a reserved extension. Non-empty (validated). |

### `SessionAnswer` (approval)
| Field | Type | Notes |
|---|---|---|
| `allow` | `bool` | Approve / deny the pending request. |
| `scope` | `"once" \| "session"` = `"once"` | Maps to `Session.answer_approval(scope=...)`. |
| `reason` | `str \| None` = `None` | Public-safe, optional. |

### `QuestionAnswer`
| Field | Type | Notes |
|---|---|---|
| `answers` | `list[str]` | Maps to `Session.answer_question(answers=...)`. |

> A run/session is selected by path id; the credential travels in a header (see Auth), never in a body.

## Response models (host → client) — metadata-only

### `HistoryEntryView` — the public-safe projection of `HistoryEntry`
| Field | Type | Source | Notes |
|---|---|---|---|
| `role` | `"user" \| "assistant"` | `HistoryEntry.role` | Metadata. |
| `block_count` | `int` | `len(HistoryEntry.blocks)` | **Count only** — the raw `blocks` (conversation content) are never serialized (FR-016, NFR-006). |

### `RunResult` — the projection of `RunOutcome`
| Field | Type | Source | Notes |
|---|---|---|---|
| `session_id` | `str` | `RunOutcome.session_id` | Public id. |
| `termination_reason` | `str` | `RunOutcome.termination_reason` | Public-safe reason. |
| `turns_taken` | `int` | `RunOutcome.turns_taken` | Count. |
| `history` | `list[HistoryEntryView]` | projected `RunOutcome.history` | Metadata-only views. |
| `consumer_failures` | `list[str]` | `RunOutcome.consumer_failures` | Public-safe failure markers. |

### `SessionSummaryView` — the projection of `SessionSummary` (from `list_sessions`)
| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | Public id. |
| `status` | `str` | Public-safe lifecycle/status string projected from `SessionSummary`. |
| (only public-safe metadata fields of `SessionSummary` are surfaced; no content) | | Exact fields finalized at implement against the public `SessionSummary` shape. |

### `OpenedSession`
| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | The id to address subsequent submit/answer/cancel/stream/inspection calls. |

### `Resolved`
| Field | Type | Notes |
|---|---|---|
| `resolved` | `bool` | Result of an out-of-band `answer_approval` / `answer_question` (unknown/stale id → `false`, never a crash). |

### `ArtifactContent`
| Field | Type | Notes |
|---|---|---|
| `reference` | `str` | The requested stable reference. |
| `content` | `str` | The retrieved artifact body (the artifact store's own content; returned only on an explicit hit). A miss returns a not-found error instead, never partial/None inline. |

### `ErrorResponse` — the one public-safe error envelope
| Field | Type | Notes |
|---|---|---|
| `detail` | `str` | A fixed, public-safe message (`"unauthorized"`, `"not found"`, `"a run is already active"`, `"invalid request"`). **Never** a stack trace, internal type name, path, or secret (FR-016, SC-003). |

## Auth types (boundary)

### `Authenticator` (injected by the embedder)
A callable verifying a request credential:
```text
Authenticator = Callable[[str | None], Awaitable[bool]]
```
- Input: the credential extracted from the request header (or `None` if absent).
- Output: `True` ⇒ admit; falsy ⇒ deny. A **raised** exception is treated as deny (fail-safe).
- A small `Principal`-returning protocol variant is allowed if useful, but the boolean form is the
  minimal contract; either way the layer persists nothing.

### `_DENY_ALL` (default)
The default authenticator when none is injected: denies every request (default-deny, FR-014).

### Auth dependency (FastAPI)
Extracts the credential, calls the `Authenticator`, and on deny raises the framework's
unauthorized error → an `ErrorResponse(detail="unauthorized")` with status 401, never echoing the
credential (FR-013/FR-015).

## Internal seams (not serialized)

### `StreamSink` (the SSE consumer) — `streaming.py`
An `EventSink`-compatible async callable bound as the run's `on_event`. For each `RuntimeEvent` it
computes `serialize_event(event)` and pushes a `data: <json>\n\n` frame onto an `anyio` memory stream
that the SSE response generator drains in order. A broken/closed channel (client disconnected) is
swallowed and recorded as a consumer failure — it never propagates into the run (FR-006, NFR-005).

### `SessionRegistry` / `SessionEntry` — `sessions.py`
Lifespan-scoped state mapping `session_id → SessionEntry`. A `SessionEntry` holds the live Phase-2
`Session` handle, its background driving task scope, and its `StreamSink` channel. Created on open,
removed on close/cancel. Honors the host's sequential-per-instance guarantee (at most one active;
otherwise 409).

## Determinism & safety invariants

- **Metadata-only responses**: no response model carries a `ContentBlock`, tool input/output, or
  secret; history is counts + roles only (FR-016, NFR-006, SC-003).
- **Verbatim stream**: SSE frames are exactly `serialize_event(event)` — the layer adds nothing and
  redacts nothing beyond what the normalized event already exposes (FR-005); order follows the
  recorded event order, never wall-clock (NFR-004, SC-002).
- **Fail-safe**: every miss/unknown id → an explicit `ErrorResponse`/`Resolved(false)`; every raising
  injected callable (authenticator, approval handler, consumer) is contained; auth defaults to deny
  (NFR-005, SC-004/005).
