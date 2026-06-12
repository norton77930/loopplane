# Contract: Agent Run Lifecycle

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-010–FR-015, FR-001, FR-003,
FR-120 | **Date**: 2026-06-13

How a session is created, driven, suspended, resumed, and terminated — independent of any
transport, host, or frontend (constitution Principle IV). Two named roles (research A2):
the **Runtime Controller** owns lifecycle; the **Dispatcher** owns the round-trip.

## Controller operations (FR-010)

| Operation | Semantics |
|---|---|
| create | Mint a new Session with identity and storage root; record session-meta; state `created → active` |
| attach | Bind the (single, A8) driving consumer's channels to the session; on an existing session, replay history first (FR-014) |
| drive | Accept user input, run the Agent Loop turn cycle until the run ends with exactly one `run-terminated` event (FR-001) |
| detach | Unbind the consumer; state `active → suspended`; in-flight work is cancelled cleanly per disconnect semantics below |
| resume | Reconstruct conversation state from durable records alone (per [checkpoint.md](./checkpoint.md)), then continue as `active` (FR-081) |
| terminate | End the session with a recorded termination; terminal state |
| list | Enumerate sessions with identity + recency metadata, newest first (FR-085) |

These lifecycle operations, together with event-stream subscription, are the **entire
sanctioned extension surface** for future scheduler/validator/evaluator layers (FR-120).

## Dispatcher channel contract (FR-011)

The Dispatcher drives the complete session round-trip using only an abstract channel pair:

- **outbound**: a sink accepting Runtime Events
  ([runtime-events.md](./runtime-events.md));
- **inbound**: a source yielding consumer requests.

Any future host (CLI, web, desktop, scheduler) supplies its own channel implementation; the
driver itself never changes.

### Inbound request vocabulary (consumer → runtime)

| Request | Payload | Semantics |
|---|---|---|
| submit-input | input blocks | Starts the next turn cycle |
| approval-decision | request_id, allow/deny, scope (once/session), optional reason | Resolves exactly one pending approval (FR-012; [approval.md](./approval.md)) |
| question-answer | request_id, answers | Resolves exactly one pending question (FR-116) |
| cancel | — | Cancellation takes effect pre-turn and mid-stream, never raises, ends the run with a `cancelled` terminal event (FR-003) |

### Pending-interaction registry (FR-012)

- Every outgoing approval request and question carries a unique `request_id`.
- Each inbound resolution matches exactly one pending entry; resolutions for unknown or
  already-resolved ids are ignored with a `diagnostic`.
- At most one resolution is ever applied per request.

### Disconnect semantics (FR-013, FR-115)

When the consumer channel closes mid-run, the Dispatcher MUST, in order:

1. cancel in-flight work cleanly (no exception escapes to the host);
2. resolve **every** pending approval as denied (`resolution source: disconnect`) and every
   pending question as unanswered-cancelled;
3. clear per-connection callbacks and registry state;
4. leave the session suspended, consistent, and resumable — and never hang.

### Replay on reattachment (FR-014, FR-015)

- Durable history replays as events with `replay: true`, bracketed by `replay-started` /
  `replay-completed`, including past user inputs — sufficient to reconstruct the visible
  conversation.
- The Dispatcher MAY batch rapid increments for delivery efficiency but MUST NOT reorder:
  any non-incremental event flushes buffered increments first.

## Concurrency rules

- One driving consumer per session at a time (research A8); a new attach replaces the old
  one only after the old channel is fully released.
- The Dispatcher serializes turns: a `submit-input` during an active turn is rejected with
  a `diagnostic` (the foundation has no input queue; queueing is a future-layer concern).
