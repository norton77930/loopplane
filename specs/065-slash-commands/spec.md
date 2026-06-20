# Feature Specification: Backend-Semantic Slash Commands

**Feature Branch**: `065-slash-commands`

**Created**: 2026-06-21

**Status**: Draft — P1 (review backlog batch 064–072, unit 2/9)

**Input**: User description: "P1 (gap G14): backend-semantic slash commands /compact /cost /model /memory on the CLI (017) + web/API — a host command surface mapping to EXISTING seams (compact_history; the 064 cost read; the model registry; the MemoryStore). MUST route through existing seams, NEVER bypass the Gateway/Event Bus. A new loopplane.commands module + CLI/webapi wiring. Additive; no ADR."

## ⚠️ Boundary note (read first)

The web UI palette (029) is frontend-only — there are NO backend-semantic commands. This unit adds a
small **host command surface** (`loopplane.commands`) with four commands that each map to an
**existing seam**: `/cost` → 064's `host.session_cost`/`monthly_spend`; `/model` → the model registry
(the existing `/models` listing); `/memory` → the `MemoryStore` (the existing memory inspection);
`/compact` → `compact_history` on a session's history via a new thin host method. **Commands route
ONLY through existing seams — they never bypass the Tool Gateway (V) or the Event Bus (VI), add no
new `TerminationReason`, and require no `SCHEMA_VERSION` bump.** Three commands are READ-ONLY; only
`/compact` mutates session state, and it does so through the same `compact_history` the loop uses.
Additive — the CLI gains "/cmd" interception (a host UX feature) and the web/API host gains a command
endpoint; the **runtime core (loop/gateway/events/content) is byte-identical**. Public-safe; no ADR.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read-only commands (/cost, /model, /memory) (Priority: P1)

A user types `/cost`, `/model`, or `/memory` (in the CLI REPL, or POSTs it to the web/API command
endpoint) and gets a host-rendered answer drawn from the existing seam, without round-tripping the
model.

**Why this priority**: These are the high-value, low-risk commands — they surface already-exposed
data (064 cost, the model registry, the memory store) as ergonomic commands (G14 parity).

**Independent Test** (offline): dispatch `/cost` for an owned budget-tracked session → the
accumulated USD (064); `/model` → the available models; `/memory` → the memory entries; each scoped
to the caller; an unknown command → a clean "unknown command" result (not a crash, not sent to the
model).

**Acceptance Scenarios**:

1. **Given** a budget-tracked session, **When** the user runs `/cost`, **Then** the result shows the
   session's accumulated USD (+ the principal's monthly spend), via 064's read seam.
2. **Given** configured models, **When** the user runs `/model`, **Then** the result lists the
   available models (the existing registry/listing).
3. **Given** a configured `MemoryStore`, **When** the user runs `/memory`, **Then** the result lists
   the memory entries (the existing memory seam), scoped to the caller.
4. **Given** any input, **When** the user runs an unknown `/command`, **Then** a clean "unknown
   command" result — never a crash, never silently sent to the model.

---

### User Story 2 - /compact mutates via the existing seam (Priority: P1)

A user runs `/compact` to compact the current session's conversation history, reusing the same
`compact_history` the loop's proactive compaction uses (not a new compaction path).

**Why this priority**: `/compact` is the one state-mutating command; it must reuse the proven seam so
behaviour matches the loop's automatic compaction exactly.

**Independent Test**: a session with a long history → `/compact` → the history is compacted (a
`SummaryMarkerBlock` per `compact_history`); a session with nothing to compact → a clean "nothing to
compact" result; no event-schema change.

**Acceptance Scenarios**:

1. **Given** a session whose history can be compacted, **When** the user runs `/compact`, **Then** the
   history is compacted via `compact_history` (the same result the loop's compaction produces).
2. **Given** a session with nothing to compact, **When** the user runs `/compact`, **Then** a clean
   "nothing to compact" result (no error, no schema change).

---

### Edge Cases

- **unknown command / bad args**: a clean normalized "unknown command" / usage result — never a crash,
  never sent to the model, never an execution path outside the existing seams.
- **command vs prompt**: a leading `/` is intercepted as a command; ordinary text is unchanged
  (byte-identical for non-command input).
- **owner-scoping**: `/cost` (064) + `/memory` are scoped to the caller's principal/session; never
  another principal's data (reuse the established ownership pattern).
- **no seam configured**: `/cost` with no budget → "not tracked" (064); `/memory` with no
  `MemoryStore` → "no memory configured"; `/compact` with nothing to compact → "nothing to compact".
- **public-safety**: command results carry no DSN/secret/internal path/another-principal's data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add a `loopplane.commands` module — a small registry that parses a leading-`/` command
  + args and dispatches to a handler; each handler maps to an EXISTING seam and returns a
  host-renderable result. Unknown command → a normalized "unknown command" result (never raises).
- **FR-002**: `/cost` → 064's `host.session_cost` / `monthly_spend` (read-only); `/model` → the model
  registry (the existing `/models` listing); `/memory` → the `MemoryStore` (the existing memory seam,
  read-only); each owner/caller-scoped.
- **FR-003**: `/compact` → compact the target session's history via the EXISTING `compact_history`
  (the loop's compaction seam) through a thin host method; reuse the loop's compaction semantics; a
  no-op when nothing to compact. No new compaction path.
- **FR-004**: Wire the command surface into the CLI (017) REPL (a leading `/` is intercepted +
  dispatched; ordinary text is unchanged) AND the web/API host (a command endpoint) — both reuse the
  one `loopplane.commands` registry + the existing seams.
- **FR-005**: Commands route ONLY through existing seams — NEVER bypass the Tool Gateway (V) or the
  Event Bus (VI); no new `TerminationReason`; no `SCHEMA_VERSION` bump; no new dependency; no ADR. The
  runtime core (loop/gateway/events/content) is byte-identical; non-command input is unchanged.
- **FR-006**: Public-safe — command results carry no DSN/secret/internal path/another-principal's
  data; owner/caller-scoped; the DSN + principal_id are never echoed.

### Key Entities *(include if feature involves data)*

- **Command**: `{ name, handler(context) -> CommandResult }` in a small registry.
- **CommandResult**: a normalized host-renderable result (text + a kind), public-safe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `/cost`, `/model`, `/memory`, `/compact` each work from the CLI + the web/API host,
  mapping to the existing seam; an unknown command returns a clean result — 100% of covered cases.
- **SC-002**: `/compact` reuses `compact_history` (the same result as the loop's compaction); no new
  compaction path; no `SCHEMA_VERSION` bump / new reason.
- **SC-003**: Non-command input is byte-identical (the runtime core unchanged); owner/caller-scoped;
  public-safe; the four gates + structural audits + the existing CLI/webapi suites pass.

## Assumptions

- Reuses 064 (`host.session_cost`/`monthly_spend`), the model registry / `/models` listing, the
  `MemoryStore` / memory inspection seam, `loopplane.loop.compaction.compact_history`, and the
  webapi/CLI host surfaces.
- **Out of scope**: model SWITCHING mid-session (read/list only for `/model`); arbitrary/custom
  user-defined commands; a full command-plugin system; frontend palette changes (029 already
  exists); command history/autocomplete; `/help` beyond a basic command list.
- Additive; the runtime core byte-identical; commands map only to existing seams; public-safe;
  offline-testable. No ADR (a host command surface over existing seams within the established
  host boundary).
