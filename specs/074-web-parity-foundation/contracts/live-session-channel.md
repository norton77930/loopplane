# Contract: Live Session Channel

## Purpose

Provide an additive authenticated bidirectional channel for web sessions while keeping existing REST/SSE endpoints available.

## Authentication

1. Browser authenticates with existing HTTP auth.
2. Browser requests a short-lived live ticket for an owned session or draft commit.
3. Browser opens the live channel with the ticket and optional `last_sequence`.
4. Server rejects expired, unknown, or non-owned tickets with a public-safe error.

Long-lived bearer tokens, provider secrets, private paths, and raw adapter errors must not appear in channel URLs or messages.

## Client Messages

| Type | Required payload | Behavior |
| ---- | ---------------- | -------- |
| `submit` | prompt text, optional session id, optional selected model, client message id | Starts or continues a session turn. |
| `abort` | session id, optional run/turn id | Stops the in-flight turn through the existing cancellation boundary. |
| `approval_decision` | request id, decision | Resolves the matching pending approval. |
| `question_answer` | question id, answer or option | Resolves the matching pending user question. |
| `ack` | highest accepted sequence | Records client progress for reconnect and diagnostics. |

Unknown types fail clearly without changing session state.

## Server Messages

| Type | Required payload | Behavior |
| ---- | ---------------- | -------- |
| `ready` | session id, latest sequence, transport status | Confirms channel readiness. |
| `event` | normalized session event | Carries replayable user-visible session history. |
| `notice` | public-safe status | Carries recoverable transport status such as replay completion. |
| `error` | public-safe code and message | Reports rejected actions or channel failure. |

## Reconnect

- Client tracks the highest accepted server sequence.
- Reconnect includes `last_sequence`.
- Server replays events after that sequence when available.
- Client dedupes by sequence or stable event identity.
- Existing REST/SSE history remains a fallback and compatibility path.

## Compatibility

- Existing `/v1/sessions/{id}/events` behavior remains available.
- Existing REST submit, cancel, approval, question, history, model, and upload flows remain behavior-compatible.
- Desktop remains compatible until unit 077 intentionally changes desktop transport behavior.
