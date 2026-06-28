# Data Model: Web Parity Foundation

## LiveSessionTicket

Short-lived credential used to open or reconnect the live session channel.

**Fields**:

- `ticket`: opaque single-use or short-lived value returned by an authenticated HTTP endpoint.
- `principal_id`: authenticated owner identity.
- `session_id`: target session, when reconnecting to an existing session.
- `expires_at`: server timestamp after which the ticket is rejected.
- `issued_at`: server timestamp used for diagnostics and tests.
- `capabilities`: optional list of allowed live-channel actions.

**Validation rules**:

- Must be issued only after normal HTTP authentication succeeds.
- Must be scoped to the authenticated principal.
- Must expire quickly and fail with a public-safe error.
- Must not expose bearer tokens, provider credentials, private paths, or internal host details.

## LiveClientMessage

Envelope sent by the browser through the live channel.

**Fields**:

- `type`: one of `submit`, `abort`, `approval_decision`, `question_answer`, or `ack`.
- `client_message_id`: client-generated idempotency key for user actions.
- `session_id`: existing session id or absent for first-send draft commit.
- `sequence`: optional highest server sequence observed by the client.
- `payload`: type-specific body.

**Payloads**:

- `submit`: prompt text, selected model id when committing a draft, and existing attachment references when supported by the current API.
- `abort`: current run or turn identifier when available.
- `approval_decision`: approval request id plus decision.
- `question_answer`: question id plus answer text or selected option.
- `ack`: highest accepted server sequence.

**Validation rules**:

- Unknown `type` values are rejected with public-safe errors.
- Mutating messages must be scoped to an owned session or a new draft commit.
- Repeated `client_message_id` values must not duplicate user-visible effects.

## LiveServerMessage

Envelope sent by the server through the live channel.

**Fields**:

- `type`: one of `ready`, `event`, `notice`, or `error`.
- `sequence`: monotonic session sequence when the message represents replayable session state.
- `session_id`: session associated with the message.
- `payload`: type-specific body.

**Payloads**:

- `ready`: channel/session status, latest known sequence, and active transport metadata.
- `event`: normalized session event already accepted by the runtime/session history.
- `notice`: recoverable transport-level status such as reconnect replay completion.
- `error`: public-safe error code and message.

**Validation rules**:

- Event payloads must correspond to declared backend contract fixtures or schemas.
- Client-visible ordering must follow server sequence.
- Error messages must not leak raw adapter errors, private paths, tokens, credentials, or query strings.

## TransportMode

Browser-side indicator for the active chat transport.

**Fields**:

- `mode`: `rest_sse` or `live`.
- `status`: `connecting`, `connected`, `reconnecting`, `degraded`, or `closed`.
- `last_sequence`: highest accepted server sequence.
- `supports_bidirectional`: boolean.

**Validation rules**:

- UI state must consume transport-neutral chat/session actions.
- REST/SSE remains a valid mode for compatibility and rollback.

## SessionSummaryExtended

Additive web-facing session list item.

**Fields**:

- Existing session summary fields, including `id`, `title`, `created_at`, and `last_active_at`.
- `model`: optional model id actually associated with the session.
- `starred`: boolean, default `false`.
- `forked_from_session_id`: optional source session id.
- `forked_from_sequence`: optional source event sequence or equivalent checkpoint marker.
- `search_snippet`: optional search result context.

**Validation rules**:

- All returned summaries must belong to the authenticated principal.
- Missing optional fields must not break existing clients.
- Star/fork metadata must survive list refresh and page reload.

## DraftChat

Browser state before a persisted session exists.

**Fields**:

- `draft_id`: local id for UI state only.
- `prompt_text`: current composer value.
- `preferred_model`: selected model id for the first send.
- `created_at`: local timestamp.

**Validation rules**:

- Must not create a backend session until first submit.
- If the preferred model is unavailable at submit time, the UI/API must fall back or fail clearly according to the model catalog contract.
- Must not store provider credentials.

## SessionFork

Request and result model for creating a new session from an existing session point.

**Fields**:

- `source_session_id`: owned source session.
- `source_sequence`: selected conversation point.
- `new_session_id`: created session id.
- `title`: optional new title.
- `model`: optional model id for future turns.

**Validation rules**:

- Source session must belong to the principal.
- Source session remains unchanged.
- Forked history must be deterministic and replayable by the same session-history APIs used elsewhere.

## BulkDeleteRequest

Request model for deleting multiple owned sessions.

**Fields**:

- `session_ids`: non-empty list of selected session ids.
- `confirm`: explicit confirmation flag.

**Validation rules**:

- Empty lists are rejected.
- `confirm` must be true.
- Only owned sessions are removed.
- Already-removed sessions are treated deterministically and do not delete non-owned sessions.
- Active-session fallback after deletion is deterministic.
