# Implementation Plan: CLI and Remote Parity

**Branch**: `079-cli-remote-parity` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/079-cli-remote-parity/spec.md`

## Summary

Bring the terminal host to parity with the web and desktop surfaces without touching the
runtime core or any outward contract.

The work splits cleanly in two. **Locally**, everything US1–US3 needs already exists behind
`LoopPlaneHost.session()` — a `Session` with `submit`, `cancel`, `answer_approval`,
`answer_question` — and the CLI simply never used it, calling `host.run()` per line instead,
which starts a new conversation every turn. Rebuilding the interactive loop on that handle
delivers a continuing conversation, terminal-side approvals and questions, and a mid-turn
interrupt that leaves the conversation open (the controller re-arms its cancellation signal
after every turn). **Remotely**, the web/API host already exposes open / submit / approve /
answer / cancel / stream-with-`Last-Event-ID` / list / command, so the bridge is a client of
those endpoints — lazily importing the already-declared `httpx`, deserializing each SSE
frame back into a `RuntimeEvent`, and rendering it through the *same* `EventRenderer` the
local path uses.

The command surface gains four read-only commands (`/help`, `/sessions`, `/permission`,
`/history`) and a `remote_safe` classification whose one meaningful refusal is `/compact` —
the only mutating command, irreversible and unverifiable from a remote view.

Net effect: no new package, no new dependency, no new endpoint, no schema change, no default
change, and no ADR.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: anyio, pydantic (base); `httpx` for the remote path only, lazily
imported from the existing `net` extra (`pyproject.toml:39`)

**Storage**: none added. Durable conversations continue to use the existing optional
checkpoint store via `--store`

**Testing**: pytest; `httpx.ASGITransport` against a real `create_app(...)` for the remote
paths

**Target Platform**: a terminal on Windows, Linux, or macOS

**Project Type**: single Python package with a console entry point (`loopplane`)

**Performance Goals**: an interrupt returns the operator to the prompt within 1 second
(SC-003); reconnection attempts are bounded rather than unlimited (FR-037)

**Constraints**: no outward web contract change; no new dependency or extra; no default-value
change (invariant G5); the terminal must import and run with only base dependencies
installed; no credential, private path, or raw exception may reach any output

**Scale/Scope**: 3 modified modules and 2 new modules under `src/loopplane/cli/`, 1 extended
module under `src/loopplane/commands/`, 2 documentation files, and roughly 7 test files

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Both passes clean.*

| Principle | Assessment |
| --- | --- |
| **I — Spec-First** | Every change traces to `specs/079-cli-remote-parity/spec.md` and to a numbered FR. Nothing speculative. |
| **II — Greenfield** | All code is written fresh for this repository. The remote client is derived from this repo's own endpoint contract, not adapted from any reference implementation. |
| **III — Harness before loop automation** | Untouched. No scheduler, validator, evaluator, or auto-iteration behavior is added; the Phase-3 engineering layer is not imported. |
| **IV — Runtime boundary clarity** | All work is inside Block 2 (`host`/`cli`/`commands`) plus documentation. No boundary is blurred, no new module boundary is introduced, and `cli`/`commands` continue to reach only public host seams. Consequently **no ADR is required**. |
| **V — Tool Gateway ownership** | The terminal executes no tool. Commands remain host UX; the new commands read `list_sessions`, `agent_controls`, and `history_snapshot` — all public host methods, none of which resolve or invoke a tool. |
| **VI — Event Bus ownership** | The terminal only consumes normalized events. The remote path consumes the *serialized* stream the web host already publishes and re-emits nothing onto any bus. No event type, payload, or `SCHEMA_VERSION` changes. |
| **VII — Public-safe** | The credential is read from the environment or an argument, held in memory, and never rendered — including in failures. Approval prompts carry only `tool_name` and `input_summary`. Poison fixtures use the synthetic markers in `tests/helpers/public_safety.py`. |
| **VIII — No SDK replacement** | No agent framework is introduced. `httpx` is an HTTP client, already declared. |
| **IX — Reference, not clone** | Terminal affordances are re-derived from this repository's own seams; the design is documented in `research.md` from source, not copied. |
| **X — Testable evolution** | Every user story gets tests (unit + integration), the boundary test is extended, and rollback is a single `git revert` — nothing persistent is introduced that would outlive it (see `quickstart.md` § Rollback). |

**Human approval gates (§E) touched**: none. No event or checkpoint schema change, no gateway
SPI change, no `PolicyVerdict` change, no boundary loosening, no new dependency or extra, no
default-value change, no outward webapi contract change, no release action.

**One specification correction carried by this plan**: research R8 found that the server's
cancel endpoint ends the live session rather than idling it, so the spec's FR-028 was restated
to match the server's existing semantics instead of changing them. Recorded in `research.md`,
confirmed as the single HIGH finding by `/speckit.analyze`, and applied to `spec.md`
(FR-028, US6 acceptance scenario 4, and Assumptions) plus `checklists/requirements.md`.

## Project Structure

### Documentation (this feature)

```text
specs/079-cli-remote-parity/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 — R1..R12, every decision read from source
├── data-model.md        # Phase 1 — command surface + remote client state
├── quickstart.md        # Phase 1 — end-to-end validation scenarios
├── contracts/
│   ├── cli-surface.md      # subcommands, options, exit codes, input grammar, output rules
│   └── command-surface.md  # loopplane.commands public API + consumed server endpoints
├── checklists/
│   └── requirements.md  # spec quality checklist (all pass)
└── tasks.md             # Phase 2 output — created by /speckit.tasks, not by this command
```

### Source code (repository root)

```text
src/loopplane/
├── commands/
│   └── __init__.py          # MODIFIED — CommandDescriptor, remote_safe, 4 new commands
└── cli/
    ├── __init__.py          # MODIFIED — re-export the new public core
    ├── app.py               # MODIFIED — `remote` subcommand; chat/resume wired to the new loop
    ├── session.py           # MODIFIED — interactive loop over host.session(); run_once unchanged
    ├── render.py            # MODIFIED — render approval and question events
    ├── prompts.py           # NEW — the shared line source + approval/question answer parsing
    └── remote.py            # NEW — the HTTP/SSE client, cursor, and reconnection

docs/
├── cli.md                   # MODIFIED — chat semantics, remote, the command list
└── api-reference.md         # MODIFIED — loopplane.commands + loopplane.cli public surfaces

tests/
├── unit/
│   ├── test_commands.py         # MODIFIED — classification, new commands, remote refusal
│   ├── test_cli_render.py       # MODIFIED — approval/question rendering
│   ├── test_cli_prompts.py      # NEW — answer parsing, defaults, safe fallbacks
│   └── test_cli_remote_stream.py# NEW — SSE frame parsing, cursor, dedup
├── integration/
│   ├── test_cli_us1.py..us5.py  # existing — must stay green
│   ├── test_cli_boundary.py     # MODIFIED — the remote module keeps the same import fence
│   ├── test_cli_interactive.py  # NEW — continuing conversation, approvals, questions, interrupt
│   └── test_cli_remote.py       # NEW — remote open/attach/submit/approve/cancel/reconnect
└── contract/
    └── test_cli_public_safety.py# NEW — credential and marker containment on both paths
```

**Structure Decision**: single-project layout, unchanged. Everything lands in the two
packages Block 2 of `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` already assigns to
the host surface — `loopplane.cli` and `loopplane.commands` — plus their tests and the two
documents Block 2 requires kept in sync.

## Design decisions carried into tasks

1. **`prompts.py` owns the single input abstraction.** Turns, approval answers, and question
   answers all pull from one line source, so the whole interactive loop stays drivable from a
   list of strings and the existing `chat_loop(host, lines, out)` test shape survives.
2. **`run_once` is not touched.** `loopplane run` stays a one-shot `host.run()` call, keeping
   that path byte-identical.
3. **Approvals are answered inside the relay.** `host.session(on_approval=…)` awaits the
   handler mid-turn; the handler renders the request and pulls the next line. A handler that
   fails still denies safely — the host already contains that (research R3).
4. **Questions are answered off the stream**, since there is no `on_question` seam: the
   renderer surfaces `QuestionAskedEvent`, and the loop answers it with
   `Session.answer_question`.
5. **Interrupt is `try/except KeyboardInterrupt` around each `submit`**, calling
   `Session.cancel()`. The controller re-arms cancellation per turn, so the conversation
   survives (research R2). At an idle prompt the existing behavior — end the conversation —
   is preserved.
6. **The remote client reuses `EventRenderer` verbatim** by running each frame's payload
   through `deserialize_event`; there is no second renderer to keep public-safe.
7. **The stream cursor advances only on a rendered frame**, and frames at or below it are
   dropped — the client half of the no-loss guarantee whose server half is `reconnect_stream`.
8. **`remote_safe` refusal happens before the handler runs**, so a refused command touches no
   host seam and reaches no server.
9. **No sidecar change.** New commands arrive at the desktop composer through the existing
   single `command.execute` method, so the six-registry discipline is not triggered.

## Complexity Tracking

No Constitution Check violations. Table intentionally empty.
