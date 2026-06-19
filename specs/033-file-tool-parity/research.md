# Phase 0 Research: File-Tool Parity

All decisions favour reuse of existing `InternalToolAdapter` mechanisms and the
dependency-light, gateway-owned baseline-tool style. No NEEDS CLARIFICATION
remained from the spec.

## Decision 1 — `edit_file` matching semantics: unique-match

- **Decision**: `edit_file` replaces a single, **uniquely-occurring** `old_string`.
  If `old_string` is absent or occurs more than once → `ErrorOutput(category=VALIDATION)`, no change.
- **Rationale**: Deterministic and safe; the model must disambiguate by
  providing more surrounding context, exactly like the reference Edit primitive
  (Constitution IX — reference, not clone). Avoids silent wrong-region edits.
- **Alternatives considered**: *Replace-all* (rejected: easy to over-edit
  unintended occurrences); *first-occurrence* (rejected: ambiguous, position-dependent).

## Decision 2 — Reuse the existing stale-write guard for `edit_file`

- **Decision**: `edit_file` reuses `_write_file`'s exact machinery — `_resolve`
  confinement, the `self._reads[(session_id, resolved_path)]` digest map,
  `_digest`, and the prior-read + unchanged check — and refreshes the recorded
  digest on success. Editing a non-existent file is a normal error (there is
  nothing to match), not a creation.
- **Rationale**: One guard, one behaviour; consistency with `write_file` and no
  duplicated safety logic. Read-before-mutate is already the adapter's contract.
- **Alternatives considered**: A separate guard for edits (rejected: duplicated
  logic, divergence risk).

## Decision 3 — `glob_files` / `grep` are pure-Python, stdlib only

- **Decision**: Implement with `pathlib`/`fnmatch` (glob) and `re` (grep). No
  external `ripgrep`/grep binary, no new dependency.
- **Rationale**: The baseline tools are deliberately dependency-light and
  cross-platform; shelling out to an external binary adds a platform/install
  burden and a second execution path outside the adapter.
- **Alternatives considered**: External ripgrep (rejected: dependency + platform
  variance); reusing `run_command` to call grep (rejected: bypasses the typed
  tool contract and portability).

## Decision 4 — Bounded results via a documented cap

- **Decision**: `grep` and `glob_files` apply a documented result cap, mirroring
  the existing `_SEARCH_MATCH_LIMIT = 100` used by `search_files`. When the cap
  is hit, results are truncated (and, for `grep`, that is observable in the
  returned text).
- **Rationale**: Prevents an unbounded result from a large tree flooding the
  model context; consistent with the existing tool's behaviour.
- **Alternatives considered**: Unbounded (rejected: context blow-up);
  per-call configurable limit (rejected: premature; the existing fixed cap is
  the established pattern).

## Decision 5 — `grep` output modes

- **Decision**: Support `content` (default — `relpath:line: text`),
  `files_with_matches` (distinct matching relative paths), and `count`
  (`relpath: N` per matching file). Invalid `output_mode` → VALIDATION error.
- **Rationale**: Matches the ergonomics of the reference Grep tool the agent is
  expected to know; the three modes cover navigation, enumeration, and triage.
- **Alternatives considered**: Single content-only output (rejected: too coarse —
  the gap this unit exists to close).

## Decision 6 — Reject a no-op `edit_file`

- **Decision**: If `old_string == new_string`, return a VALIDATION error
  ("old_string and new_string are identical; no change requested").
- **Rationale**: A no-op edit is almost always a mistake; rejecting it surfaces
  the error early and matches the reference Edit behaviour.
- **Alternatives considered**: Silent success (rejected: hides caller bugs).

## Decision 7 — Test layout

- **Decision**: Add deterministic offline tests in a focused module
  (`tests/unit/test_internal_file_tools.py`) following the construction and
  assertion patterns already used for `InternalToolAdapter`
  (`tests/unit/test_rules_and_tools.py`). Drive each tool through the adapter's
  `invoke()` and assert on `AdapterOutput` (`TextBlock` / `ErrorOutput`).
- **Rationale**: Consistent with the repo's existing tool tests; no network, no
  credentials, fully deterministic for the default gate.
