# Feature Specification: File-Edit Undo

**Feature Branch**: `054-file-undo`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "File-edit undo / rewind: snapshot a file's pre-edit content on each successful mutating file tool (write_file / edit_file / notebook_edit) and provide an undo_file tool that restores the previous version, so an agent can revert a file change in the working scope. Unit 054, Tier-3 (execution-safety & cost); closes gap G16. Additive, default-off, reuse the existing file tools + working-scope; no ADR."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent reverts a file change (Priority: P1)

After the agent edits or overwrites a file and finds the change was wrong, it calls an
**undo** tool to restore the file to the content it had immediately before that change — so a
mistaken edit is recoverable within the run without the agent having to reconstruct the old
content from memory.

**Why this priority**: This is gap G16 and the unit's core value — the reference harnesses let
an agent undo / rewind a file edit; LoopPlane has whole-session checkpoint/resume but no
targeted file-edit undo. A one-step revert makes file edits safe to attempt.

**Independent Test**: With the feature enabled, write a file, edit it, then `undo_file` it — the
file's content is exactly the pre-edit content; a second `undo_file` reverts the prior step (or
reports nothing left to undo).

**Acceptance Scenarios**:

1. **Given** the feature is enabled and a file was just modified by a mutating file tool, **When**
   the agent calls `undo_file` for that file, **Then** the file's content is restored to the
   content it had immediately before that modification.
2. **Given** a file modified twice, **When** the agent calls `undo_file` twice, **Then** the file
   walks back one step per call (most-recent-first), and an `undo_file` with no snapshot left
   reports a clear "nothing to undo".

---

### User Story 2 - Undo is bounded, scoped, and safe (Priority: P2)

Snapshots are bounded (a per-run cap, oldest-dropped), confined to the working scope, do not
interfere with the existing stale-write guard, and leave no surprise: an undo of a file the
agent has since read is reflected by the read-guard so the next edit is not falsely rejected.

**Why this priority**: An undo that corrupts the stale-write guard, grows memory unbounded, or
touches files outside the scope is worse than no undo. The snapshot mechanism must be invisible
when not used and consistent with the existing file-tool invariants.

**Independent Test**: Exceeding the snapshot cap drops the oldest; `undo_file` on a path outside
the scope / never-modified / unknown is a clear normalized error; after an undo the stale-write
guard reflects the restored content (the next edit is not rejected as stale).

**Acceptance Scenarios**:

1. **Given** more modifications than the per-run cap, **When** the cap is exceeded, **Then** the
   oldest snapshot is dropped (bounded memory) and the most recent are still undoable.
2. **Given** a restored file, **When** the agent next edits it, **Then** the stale-write guard
   does not falsely reject the edit (the guard is re-synced to the restored content).

---

### User Story 3 - Default-off and byte-identical (Priority: P3)

The feature is opt-in: when disabled, no snapshots are taken, no `undo_file` tool is offered,
and behavior is byte-identical to today.

**Why this priority**: A snapshot side-effect on every file mutation must not be imposed on hosts
that did not ask for it (memory + behavior), matching the project's default-off discipline.

**Independent Test**: With the feature disabled, the mutating file tools behave exactly as before
(no snapshot), and the tool set does not include `undo_file`.

**Acceptance Scenarios**:

1. **Given** the feature is disabled (the default), **When** the agent lists / uses the file
   tools, **Then** `undo_file` is not present and the mutating tools take no snapshot.

---

### Edge Cases

- **undo a never-modified / unknown / out-of-scope path**: a clear normalized error (no crash).
- **undo when no snapshot remains**: a clear "nothing to undo" message (not an error crash).
- **a file deleted on disk after a snapshot**: undo restores the snapshot content (re-creates it
  within the scope) or reports a clear error — resolved in planning.
- **binary / non-UTF-8 files**: the snapshot must restore the file faithfully (raw bytes), not a
  lossy text round-trip.
- **feature disabled / cap 0**: no snapshots, no `undo_file` tool (byte-identical).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When enabled, each **successful mutating file tool** (`write_file` / `edit_file` /
  `notebook_edit`) that overwrites or changes an existing file MUST first record a **snapshot** of
  the file's prior content (raw bytes), keyed per-run and per-resolved-path.
- **FR-002**: The system MUST provide an agent-facing `undo_file` tool, reachable only through the
  Tool Gateway (V), that restores a file to its most recent snapshot (most-recent-first), within
  the working scope.
- **FR-003**: `undo_file` MUST, after restoring, **re-sync the stale-write guard** so the next
  edit of that file is not falsely rejected as stale.
- **FR-004**: Snapshots MUST be **bounded** — a configurable per-run maximum (oldest dropped when
  exceeded), so memory does not grow without bound.
- **FR-005**: Snapshots + `undo_file` MUST be **confined to the working scope** (the existing
  file-tool confinement); an out-of-scope / unknown / never-modified path MUST be a clear
  normalized error; "no snapshot left" MUST be a clear non-crash message.
- **FR-006**: Snapshots MUST restore content **faithfully** for binary / non-UTF-8 files (raw
  bytes), not a lossy text round-trip.
- **FR-007**: The feature MUST be **opt-in and default-off** (byte-identical when disabled): no
  snapshots taken, no `undo_file` tool registered, no event-schema / content-model change.
- **FR-008**: The capability MUST be **additive and reuse-first** — per-session state on the
  Internal Tool Adapter (the unit-044 `todo_write` / unit-033 `self._reads` pattern), the existing
  working-scope resolution + stale-write guard; no new RunContext field / Protocol / factory, no
  loop/controller change, no new dependency, no ADR.

### Key Entities *(include if feature involves data)*

- **Snapshot**: the prior raw-bytes content of a file before a mutation, keyed by (session, resolved
  path), held in a bounded per-run history (most-recent-first).
- **Snapshot history**: the per-run, per-path stack of snapshots surfaced/consumed by `undo_file`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the feature enabled, after a mutation `undo_file` restores the exact pre-edit
  bytes in 100% of covered scenarios (text + binary); multiple undos walk back step-by-step.
- **SC-002**: After an undo, the next edit of the restored file is accepted (the stale-write guard
  is consistent) in 100% of covered scenarios; out-of-scope / unknown / empty-history each error
  cleanly.
- **SC-003**: The snapshot count never exceeds the configured cap (oldest dropped); memory is
  bounded.
- **SC-004**: With the feature disabled, behavior is byte-identical to today — the existing test
  suite passes unchanged and no event-schema / content-model change is introduced.

## Assumptions

- Snapshots live in memory on the Internal Tool Adapter, per session, bounded by a cap — the same
  class of per-session state as unit-044 `todo_write` (`self._todos`) and unit-033 (`self._reads`);
  no durable artifact store is required for v1 (an artifact-backed durable option may be a later
  follow-up but is out of scope here).
- Snapshots capture **raw bytes** so binary files restore faithfully (FR-006).
- The mutating file tools are the spec-033/046 `write_file` / `edit_file` / `notebook_edit` in the
  Internal Tool Adapter; the confinement + stale-write guard are reused as-is.
- Out of scope: cross-session / persistent undo history, a global "rewind the whole session" (that
  is checkpoint/resume's job), redo, and any UI.
- Default-off; bounded; Gateway-only (V); working-scope-confined; public-safe (VII). Per
  Constitution IX the concept is borrowed from the reference harnesses but re-derived; X keeps it
  additive + reversible.
