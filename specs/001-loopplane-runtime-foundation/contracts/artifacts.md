# Contract: Artifact Storage

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-026, FR-090–FR-094 |
**Date**: 2026-06-13

Where oversized tool output goes so conversations stay bounded without losing data.

## Offload rule (FR-090)

- A tool result whose size exceeds the configured threshold (default 64 KiB, research A3)
  is persisted **in full** as an Artifact associated with the session and the originating
  call.
- The in-conversation representation of an offloaded result carries a **bounded preview**
  plus a **stable reference** to the artifact (FR-091); the model and consumers see the
  preview + reference, never a silent truncation.

## Artifact metadata

The Artifact entity in [../data-model.md](../data-model.md): stable reference, session and
originating-call identifiers, size, media kind, creation time, opaque storage location.
Metadata is queryable; content is retrievable by reference after the run for inspection
(FR-093).

## Aggregate budget & replacement (FR-092)

- When the total size of retained tool results in a session's working history exceeds the
  configured budget (default 1 MiB, research A3), the runtime replaces the **largest
  eligible** results first with their preview + reference form.
- Replacement decisions are **frozen**: once made, a decision never changes across resume —
  resuming a session reproduces exactly the same replacement state.
- Each decision is recorded as a `replacement-decision` Checkpoint Record through the same
  durable recording boundary as all other history (FR-094); the Agent Loop itself never
  persists anything.

## Invariants

- Offload and replacement never separate a tool call from its result and never alter the
  user's verbatim recorded input.
- An artifact reference remains valid for the life of the session's stored data; retrieval
  by an unknown reference is a normal not-found error, not a crash.
- Eligibility: only tool results participate in replacement; user inputs and assistant
  messages are never replaced by this mechanism.
