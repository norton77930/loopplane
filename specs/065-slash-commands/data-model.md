# Data Model: Backend-Semantic Slash Commands

Additive host command surface over existing seams. No event/content/schema change. P1 (no ADR).

## New package: `loopplane.commands`

| Entity | Shape | Notes |
| ------ | ----- | ----- |
| `CommandContext` | `{ host, session_id: str \| None, principal_id: str, models: list[...], args: str }` | what a handler needs; built by each host's wiring. |
| `CommandResult` | `{ kind: Literal["ok","unknown","error"], text: str }` | normalized, public-safe, host-renderable. |
| `CommandRegistry` | `{ name → handler(CommandContext) -> CommandResult }` + `dispatch(line, ctx)` | parses a leading `/`; unknown → `CommandResult(kind="unknown", …)`; never raises. |
| handlers | `/cost`, `/model`, `/memory`, `/compact` | each maps to one existing seam. |

## Seam mapping (per handler)

| Command | Seam | Read/Write |
| ------- | ---- | ---------- |
| `/cost` | 064 `host.session_cost(session_id)` + `host.monthly_spend(principal_id)` | read |
| `/model` | the wiring-supplied model list (webapi `catalog` / CLI providers) | read |
| `/memory` | `host.inspect_memory(query)` | read |
| `/compact` | `host.compact_session(session_id)` → `RuntimeController.compact_session` → `compact_history(history, keep_last=_assembly_keep_last)` | write (existing seam) |

## Modified surfaces (additive)

| Surface | Change |
| ------- | ------ |
| `RuntimeController.compact_session(session_id) -> bool` | NEW: runs `compact_history` on the session; returns whether it compacted. |
| `LoopPlaneHost.compact_session` (+ a model-list accessor if needed) | NEW passthrough(s). |
| `cli/session.py` chat REPL | intercept a leading `/` → dispatch via the registry; render the result; ordinary text unchanged. |
| `webapi/app.py` `POST /commands` | NEW: dispatch a command; owner-scoped for session commands. |
| `webapi/models.py` | NEW `CommandRequest { command: str, session_id: str \| None }` + `CommandResultView { kind, text }`. |

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| registry parses `/cmd args`, dispatches, unknown → normalized result (never raises) | FR-001 |
| /cost, /model, /memory map to existing read seams; caller-scoped | FR-002 |
| /compact reuses compact_history (no new path); no-op when nothing to compact | FR-003 |
| wired into CLI REPL + webapi; one registry; non-command input unchanged | FR-004 |
| route only through existing seams; no Gateway/Event-Bus bypass; no schema/reason/dep change; no ADR | FR-005 |
| public-safe; owner/caller-scoped; no DSN/secret/path/other-principal | FR-006 |
