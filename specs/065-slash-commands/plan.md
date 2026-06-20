# Implementation Plan: Backend-Semantic Slash Commands

**Branch**: `065-slash-commands` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/065-slash-commands/spec.md`

**Boundary**: P1 (review-backlog batch 064–072, 2/9). Additive host command surface; **no ADR**.

## Summary

Add a small `loopplane.commands` registry that parses a leading-`/` command + args and dispatches to
a handler mapping to an EXISTING seam, returning a normalized host-renderable `CommandResult`. Four
commands: `/cost` → 064 `host.session_cost`/`monthly_spend`; `/model` → the available-model list
(supplied by the wiring — the webapi catalog / the CLI providers); `/memory` → `host.inspect_memory`;
`/compact` → a thin `RuntimeController.compact_session` that runs the EXISTING
`compact_history(history, keep_last=self._assembly_keep_last)` on the session. Wire it into the CLI
chat REPL (a leading `/` is intercepted + dispatched, ordinary text unchanged) and a web/API
`POST /commands` endpoint (owner-scoped for session commands). Commands route ONLY through existing
seams — never bypass the Gateway/Event Bus; the runtime core (loop/gateway/events/content) is
byte-identical; unknown command → a clean result. Public-safe; no new `TerminationReason`/`SCHEMA`
bump/dependency; no ADR.

## Technical Context

**Language/Version**: Python 3.11+; argparse/stdin CLI; FastAPI (existing `loopplane[web]`).

**Primary Dependencies**: none new — reuses 064 cost accessors, `host.inspect_memory`, the model
catalog/providers, `loopplane.loop.compaction.compact_history`, the CLI + webapi hosts.

**Storage**: none new.

**Testing**: pytest, offline: dispatch each command via the registry (unit) + the CLI REPL
interception + the webapi `POST /commands`; `/compact` compacts via `compact_history`; unknown
command → clean result; owner-scoping for `/cost`/`/compact`; public-safe; non-command input
unchanged.

**Target Platform**: cross-platform library + CLI + web host.

**Constraints**: additive; route ONLY through existing seams (no Gateway/Event-Bus bypass); runtime
core byte-identical; non-command input unchanged; owner/caller-scoped; public-safe; no schema/reason/
dependency change; no ADR. The new `loopplane.commands` package → add to `docs/api-reference.md`
(bijection).

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006. ✅
- **III. Ergonomics within bounds**: a host command surface over existing seams; no new capability
  reaches the model except via the existing paths. ✅
- **IV. Boundary**: `loopplane.commands` is a host-facing surface (like the CLI/webapi); its handlers
  call existing host/controller seams; `/compact` reuses `compact_history` (the loop's own seam). It
  does NOT import the tools layer into loop/controller; commands are not tools (no Gateway bypass —
  they invoke existing host methods, not the gateway directly). ✅
- **V. Tool Gateway**: commands are NOT a new execution path — they call existing host read seams +
  `compact_history`; no tool runs outside the Gateway. ✅
- **VI. Event Bus**: no event/`SCHEMA_VERSION`/`TerminationReason`/content change; `/compact` reuses
  the existing compaction (its existing signal, if any). ✅
- **VII. Public-safe**: results carry no DSN/secret/path/another-principal's data; owner-scoped. ✅
- **X. Testable Evolution**: Additive; runtime core byte-identical; non-command input unchanged;
  reversible; offline-tested. ✅

**Result**: PASS — a host command surface over existing seams; no ADR. Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/065-slash-commands/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/slash-commands.md
└── checklists/requirements.md
docs/api-reference.md   # + a new loopplane.commands package section (bijection)
```

### Source Code (repository root)

```text
src/loopplane/commands/__init__.py      # NEW: CommandRegistry + CommandContext + CommandResult +
                                        #   the 4 handlers (cost/model/memory/compact); parse a
                                        #   leading "/", dispatch, unknown -> normalized result
src/loopplane/controller/controller.py  # MODIFIED: + compact_session(session_id) -> bool
                                        #   (runs compact_history(session.history, keep_last=
                                        #   self._assembly_keep_last); the existing seam)
src/loopplane/host/host.py              # MODIFIED: + compact_session passthrough (mirror
                                        #   history_snapshot); a list_models accessor if needed
src/loopplane/cli/session.py            # MODIFIED: the chat REPL intercepts a leading "/" and
                                        #   dispatches via loopplane.commands (ordinary text
                                        #   unchanged); render the CommandResult
src/loopplane/webapi/app.py             # MODIFIED: + POST /commands (owner-scoped for session cmds)
src/loopplane/webapi/models.py          # MODIFIED: + CommandRequest + CommandResultView
docs/api-reference.md                   # MODIFIED: + the loopplane.commands section
tests/<slash-command tests>             # NEW
```

**Structure Decision**: One `loopplane.commands` registry shared by both hosts (DRY). A
`CommandContext` carries the host + session_id + principal_id + available_models + raw args; each
handler maps to an EXISTING seam and returns a `CommandResult` (a kind + public-safe text). The CLI
chat REPL intercepts a leading `/` (ordinary text is sent to the model unchanged — byte-identical for
non-command input); the webapi exposes `POST /commands` (the session-scoped commands `/cost`/`/compact`
go through `_owned_or_404`). `/compact` is the only mutating command — it calls a new
`RuntimeController.compact_session` that runs the EXISTING `compact_history` with the controller's
`_assembly_keep_last` (no new compaction path; the same result as the loop's proactive compaction).
`/model` lists models from the wiring-supplied source (the webapi `catalog` / the CLI providers) — a
read-only list; model SWITCHING is out of scope. Commands invoke host methods, NOT the gateway —
they are a host UX, not tools, so the no-execution-outside-the-gateway audit holds.

## Complexity Tracking

> A host command surface (a small registry) over existing seams + a thin `compact_session` reusing
> `compact_history`. Additive; runtime core byte-identical; non-command input unchanged; owner-scoped;
> public-safe; no schema/reason/dependency/ADR. Not a Constitution violation.
