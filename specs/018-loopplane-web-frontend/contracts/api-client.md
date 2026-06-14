# Contract: Web API Client

The single seam between the UI and the unit-011 web/API host. The UI consumes the
existing `/v1` API — it adds, changes, and removes nothing server-side.

## Endpoints consumed

- `POST /v1/runs/events` `{prompt}` → `text/event-stream` of normalized events.
- `POST /v1/sessions` → `{session_id}`.
- `GET  /v1/sessions/{id}/events` → `text/event-stream`.
- `POST /v1/sessions/{id}/submit` `{prompt}` → run result.
- `POST /v1/sessions/{id}/approvals/{request_id}` `{allow, scope, reason}`.
- `POST /v1/sessions/{id}/questions/{request_id}` `{answers}`.
- `POST /v1/sessions/{id}/cancel`.
- `GET  /v1/sessions` → `SessionSummary[]`.
- `GET  /v1/sessions/{id}/history`.
- `POST /v1/sessions/{id}/resume`.

## Client behavior

- Every request carries the embedder-supplied auth header (the API is default-deny);
  the header is provided at construction and **never baked into the bundle** (FR-006).
- `streamRun` / `streamSession` return an async-iterable of parsed `RuntimeEvent`s; an
  unknown event `type` is yielded but ignored by the reducer (forward-compatible).
- `fetch` is injectable, so tests run the full client against a stubbed network with no
  server and no credentials.
- An HTTP error or a dropped stream raises a typed error the UI renders as a clear
  state (FR-008) — never a crash and never a leaked secret.

## SSE parsing

Each SSE frame's `data:` line is a JSON-serialized normalized event. The parser splits
on the frame boundary and `JSON.parse`s each `data:` payload, tagging it by `type`.
Only metadata-safe fields are read (assistant text; tool name + outcome; termination
reason + turns; public-safe request ids / session ids).
