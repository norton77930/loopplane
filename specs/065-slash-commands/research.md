# Research: Backend-Semantic Slash Commands

P1 (no ADR). Additive host command surface over existing seams. No open `NEEDS CLARIFICATION`.

## Decision 1 — One `loopplane.commands` registry shared by CLI + webapi

**Decision**: A small registry `{name → handler(CommandContext) -> CommandResult}` + a parser for a
leading-`/` token. Both hosts dispatch through it; unknown command → a normalized result (never
raises).

**Rationale**: DRY (one place for the four commands); host-agnostic; testable in isolation. Mirrors
how other neutral surfaces live in their own package.

**Alternatives**: per-host ad-hoc parsing (rejected — duplication, drift).

## Decision 2 — Each command maps to an EXISTING seam (no Gateway bypass)

**Decision**: `/cost` → 064 `host.session_cost`/`monthly_spend`; `/model` → the wiring-supplied model
list (webapi `catalog` / CLI providers); `/memory` → `host.inspect_memory`; `/compact` → a new
`RuntimeController.compact_session` that runs the EXISTING `compact_history`. Handlers call host
methods, never the gateway directly.

**Rationale**: Commands are a host UX, not tools — they must not be a new execution path. Reusing the
existing seams keeps the Gateway/Event-Bus contract intact and the runtime core byte-identical.

**Alternatives**: a command that runs a tool via the gateway (rejected — that is just a tool;
commands are host-level shortcuts to existing host capabilities).

## Decision 3 — `/compact` reuses `compact_history` with the controller's keep_last

**Decision**: `RuntimeController.compact_session(session_id) -> bool` calls
`compact_history(session.history, keep_last=self._assembly_keep_last)` (the same function + config the
loop's proactive compaction uses) and returns whether it compacted; a host passthrough exposes it.

**Rationale**: Identical semantics to the loop's automatic compaction (a `SummaryMarkerBlock`); no new
compaction path; no event/schema change (reuses whatever signal the existing compaction emits).

**Alternatives**: a bespoke command-only compaction (rejected — divergent behaviour, more surface).

## Decision 4 — CLI REPL interception + webapi `POST /commands`, owner-scoped

**Decision**: The CLI chat REPL intercepts a leading `/` and dispatches (ordinary text is sent to the
model unchanged — byte-identical for non-command input). The webapi adds `POST /commands`; the
session-scoped commands (`/cost`, `/compact`) go through `_owned_or_404`; `/memory`/`/cost-monthly`
are caller-scoped.

**Rationale**: Reuse the established host input + ownership patterns; non-command input unchanged;
no cross-principal leak.

## Out of scope

Model SWITCHING mid-session (`/model` lists only); custom/user-defined commands; a command-plugin
system; the 029 frontend palette; command history/autocomplete; `/help` beyond a basic list. The new
`loopplane.commands` package is added to `docs/api-reference.md` (bijection).
