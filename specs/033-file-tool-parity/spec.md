# Feature Specification: File-Tool Parity for the Baseline Tool Set

**Feature Branch**: `033-file-tool-parity` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "LoopPlane file-tool parity. Extend the InternalToolAdapter with three additive built-in tools — edit_file (surgical unique-string replacement reusing the stale-write guard), glob_files (filename pattern matching within the working scope), and grep (regex content search with content/files/count output modes) — all confined to the run working scope and reachable only through the Gateway. Keep the existing search_files unchanged for back-compat. Pure additive backend change, no frontend, no ADR."

## Overview

The baseline internal tool set — `read_file`, `write_file`, `search_files`,
`run_command`, `ask_user`, `memory_write` — covers reading, whole-file writing,
substring search, and command execution. An agent doing real file work hits
three gaps against the capability both reference harnesses expose:

1. **No surgical edit.** Any change to an existing file must rewrite the whole
   file through `write_file`, which is token-heavy and error-prone for a
   one-line change.
2. **No filename discovery.** There is no way to enumerate files by pattern
   (e.g. `**/*.py`); the agent can only search content or guess paths.
3. **Coarse content search.** `search_files` is substring-only, capped at 100
   matches, with a single output shape and no regular-expression support.

This unit closes the gap by adding **three additive tools to the Internal Tool
Adapter** — `edit_file`, `glob_files`, and `grep` — each reachable **only
through the Tool Gateway** (Constitution V) and **confined to the run working
scope**, reusing the adapter's existing path confinement and the `write_file`
stale-write guard rather than introducing new mechanisms. The existing
`search_files` tool stays **unchanged and available** for back-compat. The
change is purely additive: the gateway, event bus, loop contract, and all other
tools are untouched (Constitution IV, X).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surgically edit an existing file (Priority: P1)

An agent reads a file with `read_file`, then changes one region of it with a
single `edit_file` call — supplying the exact `old_string` to replace and the
`new_string` to put in its place — without rewriting the whole file. The same
stale-write guard that protects `write_file` applies: the file must have been
read this session and be unchanged since.

**Why this priority**: Surgical edit is the highest-value gap — it is the
everyday file-mutation primitive an agent needs, and rewriting whole files is
the current painful workaround.

**Independent Test**: Drive the adapter through the gateway: read a file, call
`edit_file` with a uniquely-occurring `old_string`, and assert the file content
changed exactly at that region, the recorded read-digest was refreshed, and a
success result was returned.

**Acceptance Scenarios**:

1. **Given** a file read this session, **When** `edit_file` is called with an `old_string` that occurs exactly once, **Then** that occurrence is replaced by `new_string`, the file is otherwise unchanged, and the session read-digest is updated to the new content.
2. **Given** a file that was **not** read this session (or changed since the read), **When** `edit_file` is called, **Then** the edit is rejected with a normalized validation error and the file is left untouched.
3. **Given** an `old_string` that is absent or occurs **more than once**, **When** `edit_file` is called, **Then** the call is rejected with a normalized validation error and no change is made.

### User Story 2 - Discover files by pattern (Priority: P2)

An agent lists the files under the working scope that match a glob pattern
(e.g. `src/**/*.py`) to orient itself before reading or editing, getting back
working-scope-relative paths.

**Why this priority**: Filename discovery is the common precursor to reading and
editing; without it the agent must guess paths or shell out via `run_command`.

**Independent Test**: Create a small tree under the working scope, call
`glob_files` with a pattern, and assert the returned relative paths are exactly
the matching files and none resolves outside the scope.

**Acceptance Scenarios**:

1. **Given** files under the working scope, **When** `glob_files` is called with a pattern, **Then** it returns the working-scope-relative paths of the matching files (and only those).
2. **Given** a pattern that matches nothing, **When** `glob_files` is called, **Then** it returns an empty result, not an error.

### User Story 3 - Regex content search with output modes (Priority: P3)

An agent searches file contents by **regular expression** within the working
scope and chooses the output shape it needs: matching lines (`content`),
matching file paths (`files_with_matches`), or a per-file match count (`count`).

**Why this priority**: Regex search with selectable output is the power-user
search primitive; the substring-only `search_files` is kept but is too coarse
for real navigation.

**Independent Test**: Seed files with known content, call `grep` in each output
mode with a regex, and assert the results match the mode's contract; call it
with an invalid regex and assert a normalized validation error (not a crash).

**Acceptance Scenarios**:

1. **Given** files containing a pattern, **When** `grep` is called in `content` mode, **Then** it returns the matching lines with their file path and line number.
2. **Given** the same files, **When** `grep` is called in `files_with_matches` or `count` mode, **Then** it returns matching file paths, or per-file match counts, respectively.
3. **Given** an invalid regular expression, **When** `grep` is called, **Then** it returns a normalized validation error and does not raise.

### Edge Cases

- **`old_string` not found / not unique** → normalized validation error; file untouched (no "replace first occurrence" fallback).
- **`edit_file` on an unread or stale file** → the existing stale-write guard rejects it; identical contract to `write_file`.
- **Path escape** (absolute path or `..` leaving the scope) for any of the three tools → rejected by the existing working-scope confinement, consistent with the current tools.
- **`glob_files` pattern matches a directory** → directories are not returned; only files.
- **Invalid regex in `grep`** → normalized validation error.
- **Binary / undecodable files** during `grep`/`glob_files` traversal → skipped gracefully, consistent with `search_files`.
- **Large result sets** → `grep` and `glob_files` apply a documented match/result cap (mirroring `search_files`' existing 100-match cap) so a huge tree cannot produce an unbounded result.
- **`new_string` equal to `old_string`** → a no-op replacement still succeeds and refreshes the digest (idempotent), or is rejected as validation — chosen behavior documented in the plan.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unit MUST add `edit_file`, `glob_files`, and `grep` to the Internal Tool Adapter, each reachable **only through the Tool Gateway** with no bypass path (Constitution V).
- **FR-002**: `edit_file` MUST replace a **uniquely-occurring** `old_string` with `new_string` in an existing file; if `old_string` is absent or occurs more than once, the call MUST be rejected with a normalized validation error and MUST make no change.
- **FR-003**: `edit_file` MUST enforce the **same stale-write guard** as `write_file` — the target must have been read in this session and be unchanged since that read — and on success MUST update the recorded read-digest to the new content (reusing the existing guard, not a new mechanism).
- **FR-004**: `glob_files` MUST return working-scope-relative paths of **files** matching a supplied glob pattern under an optional base path (default: scope root), and MUST return an empty result (not an error) when nothing matches.
- **FR-005**: `grep` MUST search file contents by **regular expression** within the working scope and MUST support three output modes — `content` (matching lines with path and line number), `files_with_matches` (matching paths), and `count` (per-file match counts) — defaulting to `content`.
- **FR-006**: `grep` MUST treat an invalid regular expression as a normalized validation error and MUST NOT raise or crash the run.
- **FR-007**: All three tools MUST confine every path to the run working scope via the adapter's **existing confinement**; absolute paths and `..` escapes that leave the scope MUST be rejected, consistent with the current tools.
- **FR-008**: `glob_files` and `grep` MUST be declared `read_only` and `concurrency_safe`; `edit_file` MUST NOT be `read_only`.
- **FR-009**: The existing `search_files` tool MUST remain **unchanged and available** (back-compat); the new tools are additions, not replacements.
- **FR-010**: The unit MUST be **additive only** — no change to the gateway pipeline, the event bus, the loop contract, the model boundary, or any other tool (Constitution IV, X).
- **FR-011**: `grep` and `glob_files` MUST skip binary/undecodable files gracefully and MUST apply a documented result cap so a large tree cannot produce an unbounded result.
- **FR-012**: All three tools MUST be covered by deterministic, offline unit tests following the repository's existing tool-test patterns; the four quality gates MUST stay green.

### Key Entities

- **`edit_file` tool**: a mutating baseline tool performing a unique-match string replacement in an existing in-scope file, gated by the stale-write guard.
- **`glob_files` tool**: a read-only baseline tool returning in-scope, scope-relative file paths matching a glob pattern.
- **`grep` tool**: a read-only baseline tool performing regex content search with selectable output modes.
- **Working-scope confinement**: the existing path-resolution rule that rejects any path resolving outside the run's working scope (reused unchanged).
- **Stale-write guard**: the existing session read-digest map that requires a prior read and an unchanged file before a mutation, and is refreshed after a successful write/edit (reused unchanged).

### Out of Scope

- Multi-file or batch edits (a `MultiEdit`-style tool) — reserved; this unit ships single-occurrence `edit_file` only.
- Replace-all / multi-occurrence replacement semantics — `edit_file` is unique-match by design.
- Fuzzy or approximate matching for `edit_file`.
- A dependency on an external `ripgrep`/grep binary — `grep` is pure-Python, consistent with the dependency-light baseline tools.
- Any change to `search_files`, the gateway, the event bus, the loop contract, or the frontend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent can change a single region of an existing file with **one** `edit_file` call (after a `read_file`), without rewriting the file.
- **SC-002**: `edit_file` refuses — making **no** change and returning a normalized error each time — when `old_string` is missing, when it is non-unique, and when the target is unread or stale.
- **SC-003**: `glob_files` returns exactly the working-scope files matching a pattern and **never** a path outside the scope.
- **SC-004**: `grep` returns regex matches in each of the three output modes, and an invalid regex yields a normalized error rather than a crash.
- **SC-005**: `search_files` behaviour is unchanged, and the four quality gates (ruff, mypy, pytest, build) stay green with new deterministic unit tests covering all three tools.

## Assumptions

- **Pure-Python, dependency-light**: `glob_files` and `grep` are implemented with the standard library (e.g. `pathlib`/`fnmatch`/`re`), with no external binary, matching the existing baseline tools.
- **Unique-match edit semantics**: `edit_file` replaces a single, unambiguous occurrence (like the reference Edit primitive); replace-all is out of scope.
- **Reuse, don't reinvent**: the working-scope confinement and the session read-digest stale-write guard are reused exactly as the existing tools use them; no new persistence or configuration is introduced.
- **Read-before-edit**: agents read a file before editing it; the stale-write guard enforces this, identical to the current `write_file` contract.
- **Additive and reversible**: removing the three tools leaves the baseline set, the gateway, and all other components untouched (Constitution X rollback).
