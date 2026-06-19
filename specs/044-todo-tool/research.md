# Research: Agent Task List (`todo_write`)

All Technical Context items were resolved from the existing codebase; there are no open
`NEEDS CLARIFICATION` items. The decisions below record the design choices.

## Decision 1 — Where the tool lives

**Decision**: Implement `todo_write` as a handler on the existing `InternalToolAdapter`
in `src/loopplane/tools/internal.py`, added to the always-on `_DESCRIPTORS` list.

**Rationale**: It is a dependency-free, in-memory baseline tool, exactly like
`read_file` / `run_command` / `ask_user`. The adapter is already constructed and
registered as the baseline internal adapter, so adding a descriptor + a handler requires
no wiring, host/assembly, or controller change.

**Alternatives considered**: A separate adapter (rejected — unjustified new component,
violates reuse-first / IV); conditional registration like `memory_write` (rejected — that
pattern exists only because `memory_write` needs an injected `MemoryStore`; `todo_write`
has no dependency, so it belongs in the unconditional baseline).

## Decision 2 — Where the list state lives

**Decision**: Hold per-session lists in the adapter instance: `self._todos:
dict[str, list[TodoItem]]` keyed by `context.session_id`.

**Rationale**: This mirrors the existing `self._reads` map (also keyed by `session_id`),
so it reuses a proven per-run-state pattern and keeps the feature out of `RunContext`.
Not touching `RunContext` keeps the change maximally additive (no controller/`drive()`
change, unlike plan-mode/subagent-depth which had to be on `RunContext` because a *decider*
outside the adapter needed to read them — nothing outside this adapter reads the todo list).

**Alternatives considered**: A field on `RunContext` (rejected — unnecessary surface change;
no out-of-adapter reader); a global/process-level store (rejected — breaks per-session
isolation and determinism).

## Decision 3 — Write semantics

**Decision**: Set-the-whole-list (replace). Each call overwrites the session's list with
the validated submitted list; an empty list clears it.

**Rationale**: Matches the reference harnesses' TodoWrite contract and is the simplest
unambiguous semantics; the agent always sends the full current intent. Avoids a
merge/patch protocol (out of scope).

**Alternatives considered**: Per-item patch / append (rejected — more surface, ambiguous
ordering, not needed for v1).

## Decision 4 — Validation & bounds

**Decision**: Validate on write — each item must have a non-empty `content` string and a
`status` in `{pending, in_progress, completed}`; the list is bounded to a maximum (100
items). Any invalid submission yields a normalized `ErrorOutput`
(`ErrorCategory.VALIDATION`) and leaves the prior list unchanged.

**Rationale**: Fail-closed and side-effect-free on error mirrors the other handlers
(`_write_file` / `_edit_file` reject before mutating). The bound prevents unbounded
in-memory growth.

**Alternatives considered**: Silent truncation / coercion (rejected — hides agent error);
no bound (rejected — unbounded growth).

## Decision 5 — Observability surface (v1)

**Decision**: The tool returns the recorded list as a `TextBlock` result; that result is
the observable surface (the agent sees it; a host consuming the live event stream sees the
tool result). No new host endpoint and no change to the metadata-only observability overlay
(010).

**Rationale**: Keeps the change additive (VI) and minimal. The metadata-only overlay
deliberately excludes tool outputs, so the list is surfaced through the normal tool-result
path, not the overlay. A dedicated host inspection endpoint would be a separate future
unit if needed.

**Alternatives considered**: A new `/v1/inspect/todos` endpoint or a new event type
(rejected for v1 — out of scope, would touch the webapi/event surface; not required to
deliver the planning/tracking value).

## Decision 6 — No event-schema / content-model change

**Decision**: Reuse `TextBlock` for the result and `ErrorOutput` for failures; introduce no
new content block, event, or `SCHEMA_VERSION` bump; no ADR.

**Rationale**: The feature is expressible with existing primitives, satisfying Constitution
VI and X (additive, reversible).
