# Contract: Web / API Host endpoints

The network surface of `loopplane.webapi`, built by
`create_app(host, *, authenticator=None, api_prefix="/v1") -> FastAPI`. Every route is behind the
authentication boundary (US5) — an unauthenticated request never reaches the host. All paths below
omit the configurable `api_prefix` (default `/v1`). All request/response bodies are JSON except the
SSE streams (`text/event-stream`).

## Authentication (applies to every route)

- The credential is read from a request header (the `Authorization` header value). Absent ⇒ deny.
- The injected `Authenticator` decides; falsy or **raised** ⇒ deny (fail-safe). No authenticator
  injected ⇒ **deny-all** default.
- Deny ⇒ `401` with `ErrorResponse(detail="unauthorized")`; the credential is never echoed.

| Behavior | Requirement |
|---|---|
| Missing / malformed / unverifiable credential → `401` | FR-013, FR-014, SC-004 |
| Authenticator raises → `401` (not `500`) | FR-014, NFR-005 |
| Valid credential → request admitted to the host | FR-013, SC-004 |

## US1 — Run

### `POST /runs`
Start one run and return its public-safe outcome.

| | |
|---|---|
| Body | `RunRequest{prompt}` |
| `200` | `RunResult` (session_id, termination_reason, turns_taken, metadata `history`, consumer_failures) |
| `409` | `ErrorResponse(detail="a run is already active")` — a run/session is already active (sequential host, FR-003) |
| `422`/`400` | `ErrorResponse(detail="invalid request")` — malformed/empty body (FR-016) |

Drives `host.run(prompt, on_event=<buffering sink>)`; projects `RunOutcome` → `RunResult`
(metadata-only). Requirements: FR-001, FR-002, FR-003, FR-016, SC-001.

## US2 — Event stream

### `POST /runs/events`
Start one run and stream its normalized events as they occur, then a terminal frame.

| | |
|---|---|
| Body | `RunRequest{prompt}` |
| `200` | `text/event-stream`; each frame `data: <serialize_event(event)>\n\n`, in recorded order; a final `event: outcome` frame carries the `RunResult` |
| `409` | a run/session already active (FR-003) |

Drives `host.run(prompt, on_event=<StreamSink>)` in a task while the response generator drains the
SSE channel. A disconnecting/failing client is swallowed + recorded; the run still terminates
(FR-006). Requirements: FR-004, FR-005, FR-006, NFR-004, SC-002, SC-005.

## US3 — Interactive session

### `POST /sessions`
Open an interactive session.

| | |
|---|---|
| `200` | `OpenedSession{session_id}` |
| `409` | a run/session already active (sequential host, FR-003) |

Enters `async with host.session(on_event=<StreamSink>)` in a background task; registers the handle.

### `GET /sessions/{session_id}/events`
SSE stream of that session's normalized events (same framing as `POST /runs/events`). Surfaces the
`approval-requested` / `question-asked` events the client must answer. FR-004/FR-005.

### `POST /sessions/{session_id}/submit`
| Body | `RunRequest{prompt}` |
|---|---|
| `202` | accepted; the run is driven in the background, events flow on the session stream |
| `404` | `ErrorResponse(detail="not found")` — unknown session |

Calls `Session.submit(prompt)` in the session's background task. FR-007.

### `POST /sessions/{session_id}/approvals/{request_id}`
| Body | `SessionAnswer{allow, scope?, reason?}` |
|---|---|
| `200` | `Resolved{resolved}` — `false` if the id is unknown/stale (never a crash) |
| `404` | unknown session |

Calls `Session.answer_approval(request_id, allow=..., scope=..., reason=...)` out-of-band. FR-008.

### `POST /sessions/{session_id}/questions/{request_id}`
| Body | `QuestionAnswer{answers}` |
|---|---|
| `200` | `Resolved{resolved}` |
| `404` | unknown session |

Calls `Session.answer_question(request_id, answers)`. FR-008.

### `POST /sessions/{session_id}/cancel`
| `200` | `Resolved{resolved: true}` — cancels and resolves anything parked, so it never hangs (FR-009) |
|---|---|
| `404` | unknown session |

Calls `Session.cancel()` and closes the registry entry.

## US4 — Inspection (read-only, metadata-only)

### `GET /sessions`
| `200` | `list[SessionSummaryView]` — public-safe summaries from `host.list_sessions()` (FR-011) |

### `GET /sessions/{session_id}/history`
| `200` | `list[HistoryEntryView]` — metadata-only projection of `host.history_snapshot(session_id)` (FR-011, FR-016) |
|---|---|
| `404` | unknown session |

### `POST /sessions/{session_id}/resume`
| `200` | `Resolved{resolved: true}` — calls `host.resume(session_id)` (FR-011) |
|---|---|
| `404` | unknown session |

### `GET /sessions/{session_id}/artifacts/{reference}`
| `200` | `ArtifactContent{reference, content}` from `host.retrieve_artifact(session_id, reference)` |
|---|---|
| `404` | `ErrorResponse(detail="not found")` — no artifact backend configured or unknown reference (FR-012) |

## Error envelope

Every non-2xx response body is `ErrorResponse{detail}` with a fixed, public-safe `detail`. No
response ever contains a stack trace, internal type name, filesystem path, IP, or secret (FR-016,
SC-003).

## Cross-cutting guarantees

| Guarantee | Requirement |
|---|---|
| Responses are metadata-only (no raw history blocks / tool I/O) | FR-016, NFR-006, SC-003 |
| SSE frames are `serialize_event` verbatim, recorded order | FR-005, NFR-004, SC-002 |
| Disconnecting stream client never crashes/hangs the run | FR-006, SC-005 |
| Sequential host → second concurrent run/session is `409` | FR-003 |
| The host originates no outbound network egress | FR-017 |
| No tool executed by this layer; live bus never re-emitted | NFR-002, NFR-003, SC-006 |
