# Tasks: Backend-Semantic Slash Commands

**Feature**: 065-slash-commands | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive host command surface (`loopplane.commands`) over EXISTING seams, wired into the
CLI chat REPL + a webapi `POST /commands`. No ADR. Routes only through existing seams (no Gateway/
Event-Bus bypass); runtime core byte-identical; non-command input unchanged. P1 (batch 064–072, 2/9).

**Tests**: requested.

## Phase 1: The command registry (Foundational) 🎯

- [x] T001 Create `src/loopplane/commands/__init__.py` — `CommandContext` (host, session_id|None,
  principal_id, models, args), `CommandResult` (kind: Literal["ok","unknown","error"], text), and a
  `CommandRegistry` with `dispatch(line, ctx) -> CommandResult` that parses a leading `/cmd args`,
  routes to a handler, and returns `CommandResult(kind="unknown", …)` for an unknown command (never
  raises). Export the public names in `__all__`.
- [x] T002 Implement the four handlers in `loopplane.commands` (each maps to ONE existing seam,
  public-safe, caller-scoped): `/cost` → 064 `ctx.host.session_cost(session_id)` +
  `monthly_spend(principal_id)`; `/model` → `ctx.models` (the wiring-supplied list); `/memory` →
  `ctx.host.inspect_memory(args)`; `/compact` → `ctx.host.compact_session(session_id)`. Each returns
  a normalized `CommandResult` (incl. the "not tracked"/"no memory"/"nothing to compact" cases).

## Phase 2: The /compact seam (P1)

- [x] T003 In `src/loopplane/controller/controller.py`: add `compact_session(self, session_id: str)
  -> bool` — `compact_history(self._require(session_id).history, keep_last=self._assembly_keep_last)`
  (the EXISTING compaction function + config); returns whether it compacted. No new compaction path;
  reuse the existing signal. In `src/loopplane/host/host.py`: add `compact_session` passthrough (+ a
  model-list accessor only if the command wiring needs one; else the host supplies models from its
  existing source). Mirror the `history_snapshot` delegation.

## Phase 3: Host wiring (P1)

- [x] T004 In `src/loopplane/cli/session.py` (the chat REPL): intercept a leading `/` in the input
  loop → build a `CommandContext` (the host, the live session_id, principal_id, the available models
  from the CLI providers, the args) → `registry.dispatch(...)` → render the `CommandResult`; ordinary
  (non-`/`) text is sent to the model UNCHANGED (byte-identical). No tool/Gateway bypass.
- [x] T005 In `src/loopplane/webapi/app.py`: add `POST /commands` (`CommandRequest{command,
  session_id?}` → `CommandResultView`); for session-scoped commands (`/cost`, `/compact`) call
  `_owned_or_404(session_id, principal)` first; build the `CommandContext` (host, session_id,
  principal.id, the webapi `catalog` models) → dispatch → `CommandResultView`. In
  `src/loopplane/webapi/models.py`: add `CommandRequest` + `CommandResultView{kind, text}`.

## Phase 4: Docs + tests (P1)

- [x] T006 Add a `loopplane.commands` package section to `docs/api-reference.md` (the bijection test
  enumerates packages with `__all__`).
- [x] T007 Add tests: `tests/unit/test_commands.py` (the registry: each command via a fake/real host
  context; unknown → kind="unknown"; not-tracked/no-memory/nothing-to-compact cases; `/compact`
  compacts via `compact_history`) + a CLI test (a leading `/` is intercepted, ordinary text is NOT)
  + a webapi test (`POST /commands`; owner-scoped `/cost`/`/compact` → 404 for a non-owner;
  public-safe). Use benign placeholders.

## Phase 5: Gates

- [x] T008 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + non-command byte-identity). Confirm: the structural audits
  (`test_no_execution_path_outside_the_gateway` [commands call host seams, NOT the gateway; keep
  "loopplane.tools" out of loop/controller], `test_public_safety`) + the events
  serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the api-reference bijection (the new
  `loopplane.commands` section) + the existing CLI/webapi suites pass. Do NOT run the full pytest
  concurrently with a verify Workflow (MCP load flake).

## Dependencies

- T001 → T002 (handlers need the registry) + T003 (the /compact seam). T002/T003 → T004/T005 (the
  wirings). T006 with T001. T007 after T005. T008 last.

## Implementation strategy

- A new `loopplane.commands` registry + a thin `compact_session` + two host wirings. Best via a fork
  (touches the new package + controller + host + cli + webapi + models + docs); then the four gates +
  the structural audits + the events SCHEMA_VERSION/api-reference tests + an adversarial verify
  (commands route only through existing seams [no Gateway bypass]; `/compact` reuses `compact_history`;
  non-command input byte-identical; owner-scoping / no cross-principal leak; public-safety; no schema/
  reason/dependency change) before commit — Workflow if available, else MANUAL. Commit only on a clean
  review / GO; fix + re-verify FRESH otherwise.
- Additive; P1; no ADR.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-21) — 0 critical, 0 high, 2 low (informational). 100% requirement
coverage (FR-001..FR-006 and SC-001..003 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ data-model ↔ contract ↔ tasks agree (the `loopplane.commands`
registry [`CommandContext`/`CommandResult`/`dispatch`, unknown→normalized] + the four handlers over
existing seams [`/cost`→064, `/model`→the model list, `/memory`→`inspect_memory`, `/compact`→a new
`compact_session` reusing `compact_history`] + the CLI REPL interception + a webapi `POST /commands`).
**Additive host command surface**: routes ONLY through existing seams; the runtime core
(loop/gateway/events/content) is byte-identical; non-command input unchanged; no new
`TerminationReason`/`SCHEMA_VERSION` bump/dependency. No Constitution violation (I/III/IV/V/VI/VII/X).
Low notes (informational): (1) commands are a host UX that call EXISTING host methods (not the
gateway) — they are NOT tools, so `test_no_execution_path_outside_the_gateway` holds; keep the literal
"loopplane.tools" out of any new loop/controller code. (2) the NEW `loopplane.commands` package must
register a section in `docs/api-reference.md` (the bijection enumerates packages with `__all__`).
**Cleared for `/speckit-implement`.**
