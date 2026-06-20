# Research: File-Edit Undo

Additive, no open `NEEDS CLARIFICATION`. Decisions below.

## Decision 1 — Per-session adapter state (the 044/033 pattern), no new module

**Decision**: Hold snapshots on the `InternalToolAdapter` instance:
`self._snapshots: dict[tuple[str, str], list[bytes]]` keyed by `(session_id, resolved_path)`, a
most-recent-first stack. Same class of state as unit-044 `self._todos` + unit-033 `self._reads`.

**Rationale**: Reuse-first + the lightest possible footprint; no `RunContext`/Protocol/factory/
supervisor needed (unlike 048-051) because there is no concurrency scope — undo is synchronous
adapter state.

**Alternatives considered**: a per-run supervisor + neutral context Protocol (the 048-051 pattern)
— rejected as overkill (no concurrency, no cross-component sharing); a durable artifact-store-
backed history — deferred (out of scope; v1 is in-memory).

## Decision 2 — The gate is a ctor param, not a RuntimeConfig field

**Decision**: `InternalToolAdapter.__init__(..., max_file_snapshots: int = 0)` (default 0 = off),
the existing `memory_store` injection shape. `undo_file` is registered (in `describe()`) and the
snapshot side-effect runs **only when `max_file_snapshots > 0`**.

**Rationale**: `InternalToolAdapter` is **caller-constructed and passed via
`RuntimeConfig.tool_adapters`** (assembly registers it as-is at `host/assembly.py:137`; it never
builds it). A `RuntimeConfig.max_file_snapshots` field would NOT auto-wire to the adapter → a dead
knob. The ctor param is the correct default-off gate; a host opts in by constructing
`InternalToolAdapter(max_file_snapshots=N)`.

**Alternatives considered**: a RuntimeConfig field + assembly building a default InternalToolAdapter
— rejected (assembly does not build it; would be a larger, needless change). Always-on (like
044/046) — rejected (the spec wants default-off + no `undo_file` when disabled).

## Decision 3 — Snapshot raw bytes (binary-faithful)

**Decision**: Snapshot the file's prior content as **raw bytes** (`path.read_bytes()`) before the
overwrite; `undo_file` restores via `path.write_bytes(...)`. Faithful for binary / non-UTF-8 files
(FR-006), avoiding the lossy `decode(errors="replace")` text round-trip the edit path uses.

**Rationale**: An undo must restore exactly what was there; bytes are exact.

## Decision 4 — Snapshot only existing-file overwrites; re-sync the stale-write guard

**Decision**: Take a snapshot only when a mutating tool **overwrites an existing file** (a brand-new
file has no prior content; undo of a create = a deferred nicety, out of v1 unless trivial). After
`undo_file` restores, set `self._reads[(session_id, resolved_path)] = _digest(restored_bytes)` so
the next `edit_file` is **not falsely rejected as stale** (FR-003).

**Rationale**: The stale-write guard (`self._reads`) compares the on-disk digest to the last
read/written digest; an undo changes the on-disk content, so the guard must be re-synced or the
next edit errors.

**Alternatives considered**: clearing the guard entirely — rejected (re-syncing to the restored
content is precise + preserves the guard's protection).

## Decision 5 — Bounded, scoped, contained

**Decision**: `max_file_snapshots` caps the per-run snapshot count (oldest dropped when exceeded;
a simple global cap across paths, or per-path depth — settle in tasks; global total is simplest +
satisfies the memory guard). `undo_file` reuses `_resolve` (working-scope confinement); an
out-of-scope / unknown / never-snapshotted path → a normalized `ErrorOutput`; an empty history →
a clear "nothing to undo" `TextBlock` (not a crash).

**Rationale**: Mirrors the bounded + contained + scoped posture of the other tools; `_resolve`
already rejects `..`/absolute escapes.

## Decision 6 — Tool surface

**Decision**: One Gateway tool — `undo_file(path: str)` — restores the most recent snapshot for
`path`. `read_only=False` (it mutates the file), `concurrency_safe=False`.

**Rationale**: A single, obvious revert verb; matches the reference harnesses' undo/rewind intent
mapped to the file-tool surface.

**Alternatives considered**: an argument-less "undo last edit across any file" — rejected (a
path-targeted undo is clearer + safer than guessing the last-touched file).
