# Contract: Checkpoint

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-080–FR-085, FR-094 |
**Date**: 2026-06-13

Durable, append-only session records: the source of truth a session can always be rebuilt
from.

## Record stream

- Records use the envelope and kinds defined in [../data-model.md](../data-model.md):
  session-meta, user-input, assistant-message, tool-result, replacement-decision,
  termination.
- **Append-as-you-go**: every accepted user input, assistant message, tool result, and
  termination is appended *as it occurs*, never batched at run end (FR-080). Each append is
  flushed before the operation that produced it is considered complete.
- **Serialized writes**: concurrent record writes within one session never interleave or
  corrupt the stream (FR-084) — enforced by a per-session writer lock.
- **The Agent Loop never writes records.** All persistence flows through the recording
  boundary owned by the Controller/recording component (FR-094); this includes artifact
  replacement decisions ([artifacts.md](./artifacts.md)).

## Resume (FR-081–FR-083)

Resuming a session from its records alone MUST:

1. read the record stream in sequence order;
2. **skip** any record that fails to parse or validate, surfacing a `diagnostic` warning,
   while all remaining records still load (FR-083);
3. rebuild conversation history, replacement state, and session metadata with no in-process
   state from the prior run (FR-081);
4. **repair** any incomplete tool interaction — a recorded tool-call with no recorded
   tool-result — by inserting an error-marked synthetic result, surfacing a `diagnostic`
   warning that identifies the repaired call (FR-082);
5. yield a history equal to all completed steps, ready for the next turn (SC-003).

## Listing (FR-085)

- Sessions list with identity and recency metadata, ordered most recent first.
- A storage root that does not exist yet yields an **empty listing**, not an error; first
  use creates it.

## Storage location (research A10)

- Default: a runtime-owned base directory in the platform's user-data location.
- Hosts override via runtime configuration; tests always point into temporary directories.
- The record format is line-oriented JSON (research R6) — but consumers of this contract
  depend only on the semantics above, never on the on-disk layout.
