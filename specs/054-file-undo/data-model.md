# Data Model: File-Edit Undo

Additive; in-memory per-session adapter state only. No new content block / event / RunContext
field / Protocol.

## InternalToolAdapter additions

| Member | Type | Notes |
| ------ | ---- | ----- |
| `max_file_snapshots` (ctor param) | `int = 0` | The gate + per-run cap. `0` (default) = off → no snapshot, no `undo_file` in `describe()`, byte-identical. The `memory_store` injection pattern. |
| `self._snapshots` | `dict[tuple[str, str], list[bytes]]` | `(session_id, resolved_path) → most-recent-first stack of prior raw-bytes contents`. |

## Snapshot (conceptual)

| Field | Type | Notes |
| ----- | ---- | ----- |
| key | `(session_id, resolved_path)` | Per-session, per-resolved-path (the `_resolve` confinement output). |
| content | `bytes` | The file's exact prior content (raw bytes; binary-faithful). |
| order | stack | Most-recent-first; `undo_file` pops the top; oldest dropped at the cap. |

## Behavior rules (from FRs)

| Rule | Source |
| ---- | ------ |
| Snapshot prior raw bytes before a successful overwrite by write_file / edit_file / notebook_edit (only when enabled + the file existed) | FR-001 |
| `undo_file(path)` restores the most recent snapshot (most-recent-first), Gateway-only | FR-002 |
| After restore, re-sync `self._reads[(session, path)] = _digest(restored)` | FR-003 |
| Bounded by `max_file_snapshots` (oldest dropped) | FR-004 |
| Confined to the working scope (`_resolve`); out-of-scope/unknown → normalized error; empty history → clear "nothing to undo" | FR-005 |
| Raw bytes restore binary faithfully | FR-006 |
| Default-off (`max_file_snapshots = 0`) byte-identical; no `undo_file` registered | FR-007 |
| No new RunContext/Protocol/factory; no loop/controller/event/content change; no ADR | FR-008 |

## Gating

- `describe()` returns the baseline descriptors + `undo_file` **only when** `max_file_snapshots > 0`.
- The snapshot side-effect in the three mutating handlers runs **only when** `max_file_snapshots > 0`
  (one guarded line each), so the off-path is byte-identical.
