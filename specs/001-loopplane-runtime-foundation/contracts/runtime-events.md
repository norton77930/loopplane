# Contract: Runtime Events

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-060–FR-065, FR-002, FR-005,
FR-014, FR-015 | **Date**: 2026-06-13

The Runtime Event Bus's outward vocabulary: the only language the Agent Loop speaks to the
outside world (constitution Principle VI). Inward consumer requests are specified in
[run-lifecycle.md](./run-lifecycle.md). Any change to this contract is a governed contract
change: versioned, specified, and tested before adoption (FR-065).

## Envelope

Every event carries:

| Field | Type | Notes |
|---|---|---|
| type | string | One of the closed vocabulary below |
| schema_version | integer | Vocabulary-wide; additive evolution within a version (research A4) |
| session_id | identifier | |
| sequence | integer | Monotonic per session; gap-free within a process lifetime |
| occurred_at | timestamp | |
| replay | boolean | `true` when re-emitted during history replay (FR-014) |
| payload | type-specific | |

## Vocabulary (runtime → consumer)

| Type | Payload | Emitted when |
|---|---|---|
| user-input | verbatim input blocks | A user input is accepted into a turn; re-emitted with `replay: true` so the stream alone reconstructs the visible conversation (FR-014, SC-001) |
| assistant-output-increment | text fragment, turn index | Model output streams |
| assistant-reasoning-increment | reasoning fragment, turn index | Model reasoning streams (when the model exposes it) |
| turn-completed | turn index, stop reason, token usage (input, output, cached, reasoning) | A model turn finishes (usage feeds FR-102 and future cost layers) |
| tool-call-started | call_id, tool name, validated input | The Gateway begins a call |
| tool-call-completed | call_id, outcome, bounded outputs (preview + artifact reference when offloaded), normalized error (on failure), duration | The call resolves — success, failure, denial, or timeout (FR-004, FR-024, FR-025, FR-091) |
| approval-requested | request_id, call_id, tool name, input summary | An "ask" decision escalates to the reviewer (FR-112) |
| approval-resolved | request_id, decision, scope, resolution source (reviewer, rule, session-memory, disconnect) | The pending approval resolves (auditability, SC-005) |
| question-asked | request_id, structured questions | The agent asks the user a non-permission question (FR-116) |
| question-answered | request_id, answers | The user's answer is matched to its request |
| replay-started / replay-completed | counts | Bracket the replayed span on reattachment, so consumers know when the live stream begins |
| diagnostic | severity (info, warning, error), category, safe message | A non-fatal condition: external server failure (FR-043), skipped skill/memory entry (FR-051, FR-071), repaired tool call (FR-082), skipped corrupt record (FR-083) |
| run-terminated | reason (natural-completion, turn-budget-exhausted, cancelled, unrecoverable-error), turns taken | Exactly once per run (FR-001) |

## Ordering rules

1. Event order is deterministic and consistent with execution (FR-002, NFR-001).
2. Tool-call events keep the calls' original request order regardless of completion timing
   when calls run in parallel (FR-005).
3. Increments MAY be batched for delivery, but any non-incremental event forces buffered
   increments to flush first; nothing is ever reordered (FR-015).
4. `run-terminated` is the final event of a run; nothing follows it for that run.

## Delivery & compatibility

- Consumers MUST tolerate unknown event types by skipping them (FR-063).
- Events serialize and deserialize losslessly across a process boundary (FR-064, NFR-006);
  the serialized form is self-describing (type + schema_version always present).
- The event stream plus the session lifecycle operations form the entire sanctioned
  extension surface for future layers (FR-120–FR-122): a consumer that needs more than this
  contract is a spec change, not a workaround.

## Versioning

- One `schema_version` integer for the whole vocabulary.
- Within a version: only additions (new types, new optional payload fields).
- Removals, renames, or semantic changes bump the version, update this document, and add
  contract tests before adoption (FR-065).
