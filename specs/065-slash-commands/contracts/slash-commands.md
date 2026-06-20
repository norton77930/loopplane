# Contract: Backend-Semantic Slash Commands

A host command surface (`loopplane.commands`) over EXISTING seams, wired into the CLI + web/API.
Additive; routes only through existing seams (no Gateway/Event-Bus bypass); runtime core
byte-identical. P1 (no ADR).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `loopplane.commands` | `CommandRegistry.dispatch(line, ctx) -> CommandResult` | NEW package; `/cost /model /memory /compact`; unknown → normalized. |
| `RuntimeController.compact_session` | `(session_id) -> bool` | runs the existing `compact_history`. |
| `LoopPlaneHost.compact_session` (+ model-list accessor) | passthrough | mirrors `history_snapshot`. |
| CLI chat REPL | leading `/` intercepted | ordinary text unchanged. |
| `POST /commands` | `CommandRequest{command, session_id?}` → `CommandResultView{kind, text}` | owner-scoped for session commands. |

## Behavior

| Case | Result |
| ---- | ------ |
| `/cost` on an owned budget-tracked session | the session's accumulated USD + the principal's monthly spend (064), public-safe. |
| `/model` | the available models (read-only list); no switching. |
| `/memory` | the memory entries (`host.inspect_memory`), caller-scoped. |
| `/compact` on a compactable session | the history is compacted via `compact_history` (same as the loop); returns compacted=true. |
| `/compact` with nothing to compact | a clean "nothing to compact" result (no error, no schema change). |
| unknown `/command` | `CommandResult(kind="unknown", …)` — never a crash, never sent to the model. |
| ordinary (non-`/`) input | unchanged — sent to the model as today (byte-identical). |
| `/cost`/`/compact` on a non-owned session | 404 / denied (owner-scoped via `_owned_or_404`). |

## Invariants

- Commands route ONLY through existing seams (064 cost, the model list, `inspect_memory`,
  `compact_history`) — they NEVER bypass the Tool Gateway (V) or the Event Bus (VI); they are a host
  UX, not tools; the no-execution-outside-the-gateway audit holds.
- `/compact` reuses `compact_history` with the controller's `_assembly_keep_last` — no new compaction
  path; same result + signal as the loop's proactive compaction; no event/`SCHEMA_VERSION` change.
- Additive: the runtime core (loop/gateway/events/content) is byte-identical; non-command input is
  unchanged; no new `TerminationReason`/dependency/ADR.
- Owner/caller-scoped; public-safe (no DSN/secret/internal path/another-principal's data).
- The new `loopplane.commands` package is registered in `docs/api-reference.md` (bijection).
- Out of scope: model switching; custom commands; the 029 frontend palette; history/autocomplete.
