---

description: "Task list for unit 079 — CLI and Remote Parity"
---

# Tasks: CLI and Remote Parity

**Input**: Design documents from `/specs/079-cli-remote-parity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED (Constitution Principle X). Every behavior slice gets a focused failing
test before its implementation.

**Organization**: grouped by user story so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US7 from spec.md; Setup / Foundational / Polish carry no story label
- Every task names its exact file path

## Standing constraints (apply to every task)

- No task may change an event or checkpoint schema, the gateway SPI, a default value, or the
  outward web/API contract. **If a task appears to need one of those, stop and ask.**
- `run_once` and the `loopplane run` path stay byte-identical.
- `CommandContext.remote` defaults to `False`; `remote_safe` defaults to `True`. All three
  existing command consumers must stay byte-identical.
- No new dependency and no new extra. `httpx` is imported lazily inside
  `src/loopplane/cli/remote.py` only, guarded by `try/except ImportError`.
- No Desktop sidecar RPC method is added — the six-registry discipline must NOT be triggered.
- Command handlers must be synchronous (`_Handler` is sync).
- Poison fixtures use only the synthetic markers in `tests/helpers/public_safety.py`.
- Gates: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` (**bare** —
  passing paths reports falsely), `uv run pytest -q`.

---

## Phase 1: Setup

**Purpose**: correct the one specification defect the acceptance tests depend on. The project
itself needs no initialization — 079 extends an existing package.

- [x] T001 Restate FR-028 in `specs/079-cli-remote-parity/spec.md` to match the server's existing cancel semantics: the operator can interrupt a running remote turn; the terminal reports that interruption ends the live remote connection; the conversation remains listed and its history remains available. Update US6 acceptance scenario 4 to match, and add a line to the Assumptions section recording why (research R8, `src/loopplane/webapi/app.py:709-716`). *(Applied during `/speckit.analyze` as a minimal consistency fix.)*
- [x] T002 Add the same correction note to `specs/079-cli-remote-parity/checklists/requirements.md` Notes so the checklist records that the spec changed after its first validation pass. *(Applied during `/speckit.analyze`.)*

**Checkpoint**: spec and reality agree; acceptance criteria are implementable as written.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the single input abstraction every interactive story reads from, and the
regression baseline that proves the untouched paths stay untouched.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [x] T003 Write a focused failing unit test in `tests/unit/test_cli_prompts.py` for a line source that: yields lines from an iterable, reports exhaustion distinctly from an empty line, and parses an approval answer (`y`/`yes` → allow-once, `n`/`no` → deny-once, `a`/`always` → allow-session, `never` → deny-session, anything else → deny-once).
- [x] T004 Create `src/loopplane/cli/prompts.py` with the minimal line source and answer parsing that makes T003 pass. No host import, no I/O of its own — it wraps the iterable the caller supplies.
- [x] T005 Write a failing unit test in `tests/unit/test_cli_prompts.py` for question-answer reading: a pending question consumes the next line; an empty line answers with an empty string rather than blocking.
- [x] T006 Extend `src/loopplane/cli/prompts.py` to satisfy T005.
- [x] T007 Add a regression test in `tests/integration/test_cli_us1.py` (or the nearest existing CLI suite) asserting `loopplane run <prompt>` still performs exactly one run and renders the same output shape, so later phases cannot silently change the one-shot path.

**Checkpoint**: one input abstraction exists and is tested; the one-shot path is pinned.

---

## Phase 3: User Story 1 — Continuous conversation (Priority: P1) 🎯 MVP

**Goal**: every turn typed at the terminal belongs to one conversation, and a stored
conversation can be picked up interactively.

**Independent Test**: state a fact in turn one, refer to it in turn two, observe the answer
uses it; both turns report the same session id. With `--store`, quit and resume, then
continue.

### Tests for User Story 1

- [x] T008 [P] [US1] Write a failing integration test in `tests/integration/test_cli_interactive.py` driving `chat_loop` with two lines and a scripted model, asserting both turns run against one session id and the second turn's assembled context includes the first turn.
- [x] T009 [P] [US1] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting the conversation closes cleanly at EOF and at `quit`, leaving no pending approval or question unresolved.
- [x] T010 [P] [US1] Write a failing integration test in `tests/integration/test_cli_interactive.py` for interactive resume: with a durable store, a stored conversation is picked up and a further turn continues the same session id.
- [x] T011 [P] [US1] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting that with no durable store configured, resume prints a public-safe explanation and returns exit code 1 without raising.

### Implementation for User Story 1

- [x] T012 [US1] Rewrite `chat_loop` in `src/loopplane/cli/session.py` over `LoopPlaneHost.session(...)`: open once, submit each non-command line through `Session.submit`, close via `aclose()` on EOF/`quit`. Keep the `(host, lines, out)` signature so the existing suites keep driving it. Leave `run_once` untouched.
- [x] T013 [US1] Wire the command path in `src/loopplane/cli/session.py` to the open conversation's session id so `/cost` and `/compact` scope to it, replacing the `last_session_id` tracking.
- [x] T014 [US1] Add an interactive resume core to `src/loopplane/cli/session.py` built on `LoopPlaneHost.resume_session(...)`, reusing the same loop body as `chat_loop`.
- [x] T015 [US1] Update the `resume` subcommand in `src/loopplane/cli/app.py` to enter the interactive resume loop, keeping the existing public-safe failure text and exit code 1 for the unresumable case.

**Checkpoint**: the terminal holds a real conversation; US1 is independently demonstrable.

---

## Phase 4: User Story 2 — Approvals and questions in the terminal (Priority: P1)

**Goal**: a permission request or an agent question is presented in the terminal and answered
there, and nothing is left waiting when the operator leaves.

**Independent Test**: run a turn whose tool needs approval; answer allow/deny at both scopes;
answer a question; abandon a pending request and confirm the run does not hang.

### Tests for User Story 2

- [x] T016 [P] [US2] Write a failing unit test in `tests/unit/test_cli_render.py` asserting `EventRenderer` renders `ApprovalRequestedEvent` using only `tool_name` and `input_summary`, and renders `QuestionAskedEvent` with its text and options — and that neither renders raw tool input or output.
- [x] T017 [P] [US2] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting an approval request is answered from the next input line, that `once` re-asks on the next equivalent request and `session` does not, and that an unrecognized answer denies once.
- [x] T018 [P] [US2] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting a question asked mid-turn is answered from the next input line and the turn continues.
- [x] T019 [P] [US2] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting that ending the conversation with a request pending resolves it (approval denied, question cancelled) and the run terminates rather than hanging.

### Implementation for User Story 2

- [x] T020 [US2] Extend `EventRenderer` in `src/loopplane/cli/render.py` to render approval requests and questions per T016, keeping every existing branch byte-identical.
- [x] T021 [US2] Pass an `on_approval` handler to `host.session(...)` in `src/loopplane/cli/session.py` that renders the request and reads the decision through `prompts.py`, returning an `ApprovalDecision`.
- [x] T022 [US2] Track the pending question request id in the interactive loop in `src/loopplane/cli/session.py` and resolve it with `Session.answer_question` using the next input line.
- [x] T023 [US2] Ensure the loop's exit path calls `Session.cancel()`/`aclose()` so pending requests resolve on the way out, satisfying T019.

**Checkpoint**: the terminal can supervise a gated agent end to end.

---

## Phase 5: User Story 3 — Interrupt a running turn (Priority: P1)

**Goal**: a turn already in flight can be stopped, returning the operator to the prompt with
the conversation intact.

**Independent Test**: interrupt a streaming turn; the prompt returns; the next line continues
the same session id; interrupting at an idle prompt still ends the conversation.

### Tests for User Story 3

- [x] T024 [P] [US3] Write a failing integration test in `tests/integration/test_cli_interactive.py` using a scripted model that raises `KeyboardInterrupt` mid-turn, asserting the turn stops, `[interrupted]` is rendered, and a following line runs against the same session id. Cover **both** points FR-011 names: an interrupt raised before the turn's work begins, and one raised while output is streaming.
- [x] T025 [P] [US3] Write a failing integration test in `tests/integration/test_cli_interactive.py` asserting an interrupt raised while an approval is pending leaves no unresolved request.
- [x] T026 [P] [US3] Write a regression test in `tests/integration/test_cli_interactive.py` asserting that an interrupt at the idle prompt still ends the interactive conversation, preserving the pre-079 behavior of `_stdin_lines`.

### Implementation for User Story 3

- [x] T027 [US3] Wrap each `Session.submit(...)` in `src/loopplane/cli/session.py` in `try/except KeyboardInterrupt`, calling `Session.cancel()` and rendering `[interrupted]`, then continuing the loop — relying on the controller re-arming cancellation per turn (research R2).
- [x] T028 [US3] Confirm `_stdin_lines` in `src/loopplane/cli/app.py` keeps its EOF/`KeyboardInterrupt` exit semantics unchanged, and document the two distinct interrupt meanings in its docstring.

**Checkpoint**: all three P1 stories are done; the local terminal is at parity.

---

## Phase 6: User Story 4 — More built-in commands (Priority: P2)

**Goal**: four read-only commands land on all three consuming surfaces from one definition.

**Independent Test**: invoke each new command from the terminal and from `POST /v1/commands`
and compare results; confirm the four existing commands are unchanged.

### Tests for User Story 4

- [x] T029 [P] [US4] Write a failing unit test in `tests/unit/test_commands.py` for `CommandRegistry.describe()` returning `CommandDescriptor(name, summary, remote_safe)` for every registered command, sorted by name.
- [x] T030 [P] [US4] Write a failing unit test in `tests/unit/test_commands.py` for `/help` listing every available command with a one-line summary.
- [x] T031 [P] [US4] Write a failing unit test in `tests/unit/test_commands.py` for `/sessions`, `/permission`, and `/history` reading only `list_sessions`, `agent_controls`, and `history_snapshot`, rendering metadata only — no message content, no rule expressions — and answering public-safe text when no session is open or a seam fails.
- [x] T032 [P] [US4] Write a failing unit test in `tests/unit/test_commands.py` pinning the four existing commands' exact output for unchanged inputs, plus the unknown-command result (FR-017) and the non-command result, so the extension cannot alter any of them.

### Implementation for User Story 4

- [x] T033 [US4] Add `CommandDescriptor` and the internal per-command spec to `src/loopplane/commands/__init__.py`, extend `register` with keyword-only `summary` and `remote_safe` (defaults `""` and `True`), add `describe()`, and export `CommandDescriptor` in `__all__`. `names`, `is_command`, and the dispatch behavior stay unchanged in this task.
- [x] T034 [US4] Extend the `_CommandHost` protocol in `src/loopplane/commands/__init__.py` with the synchronous seams `list_sessions()`, `agent_controls(session_id)`, and `history_snapshot(session_id)`.
- [x] T035 [US4] Implement the `/sessions`, `/permission`, and `/history` handlers in `src/loopplane/commands/__init__.py`, each public-safe and each degrading to a normalized result when its seam is unavailable.
- [x] T036 [US4] Implement `/help` in `src/loopplane/commands/__init__.py` as a closure over the registry built in `default_registry()`, and register all four new commands with summaries.

**Checkpoint**: the command surface is richer on all three hosts, with the existing four pinned.

---

## Phase 7: User Story 5 — Remote-safety classification (Priority: P2)

**Goal**: every command declares whether it may run remotely, and the refusal happens before
any host seam is touched.

**Independent Test**: dispatch `/compact` with `remote=True` and observe a public-safe refusal
with the compaction seam never called; dispatch it with `remote=False` and observe unchanged
behavior.

### Tests for User Story 5

- [x] T037 [P] [US5] Write a failing unit test in `tests/unit/test_commands.py` asserting that with `CommandContext(remote=True)` a `remote_safe=False` command returns `kind="error"` with the fixed refusal text **and that its host seam was never called** (use a host double that records calls).
- [x] T038 [P] [US5] Write a failing unit test in `tests/unit/test_commands.py` asserting `/compact` is registered `remote_safe=False` and every other built-in is `remote_safe=True`.
- [x] T039 [P] [US5] Write a failing unit test in `tests/unit/test_commands.py` asserting `/help` lists only remote-safe commands when `remote=True` and every command when `remote=False`.
- [x] T040 [P] [US5] Write a unit test in `tests/unit/test_commands.py` asserting that a default-constructed `CommandContext` has `remote is False`, so existing consumers are unaffected.

### Implementation for User Story 5

- [x] T041 [US5] Add `remote: bool = False` to `CommandContext` in `src/loopplane/commands/__init__.py`.
- [x] T042 [US5] Add the refusal branch to `CommandRegistry.dispatch` in `src/loopplane/commands/__init__.py`, evaluated after the handler is resolved and before it is called; leave the unknown-command and exception branches untouched.
- [x] T043 [US5] Register `/compact` with `remote_safe=False` in `default_registry()` in `src/loopplane/commands/__init__.py`, and make `/help` filter by `ctx.remote`.
- [x] T044 [US5] Verify no Desktop sidecar change is required: confirm `_DESKTOP_METHOD_NAMES` in `apps/desktop/sidecar/bridge.py` is unchanged and `tests/integration/test_desktop_sidecar.py` still passes without edits. If either would need to change, **stop** — the design has drifted from research R10.

**Checkpoint**: the policy exists, is enforced client-side, and changed nothing else.

---

## Phase 8: User Story 6 — Drive a remote agent (Priority: P3)

**Goal**: the terminal can open or attach to a conversation on a remote server, stream it,
answer its requests, and interrupt it.

**Independent Test**: against a real `create_app(...)` over an in-process transport, open,
submit, answer one approval, run one command, interrupt, and disconnect.

### Tests for User Story 6

- [x] T045 [P] [US6] Write a failing unit test in `tests/unit/test_cli_remote_stream.py` for SSE frame parsing: split on blank lines, read `id:` when present, pass `data:` to `deserialize_event`, drop frames that deserialize to `None`, and drop frames whose sequence is at or below the cursor.
- [x] T046 [P] [US6] Write a failing integration test in `tests/integration/test_cli_remote.py` that builds a real app via `create_app(...)`, connects with `httpx.ASGITransport`, opens a conversation, submits a turn, and asserts the rendered output matches what the local renderer produces for the same events.
- [x] T047 [P] [US6] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting a remote approval and a remote question are answered from terminal input and the turn continues.
- [x] T048 [P] [US6] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting a remote interrupt stops the turn, reports that the live remote connection ended (per the corrected FR-028), and that the conversation is still listed afterwards.
- [x] T049 [P] [US6] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting attaching to a session another principal owns and attaching to a nonexistent id produce the **same** public-safe outcome.
- [x] T050 [P] [US6] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting a remote `/compact` is refused client-side and never reaches `POST /v1/commands`, while `/cost` is forwarded and rendered.
- [x] T051 [P] [US6] Write a failing unit test in `tests/unit/test_cli_remote_stream.py` for the failure surfaces: missing credential, rejected credential, unreachable server, and absent optional capability each produce a public-safe message and exit code 1, with the credential value never appearing in the output.

### Implementation for User Story 6

- [x] T052 [US6] Create `src/loopplane/cli/remote.py` with the lazy `httpx` import guarded by `try/except ImportError`, the `RemoteEndpoint` and `StreamCursor` shapes from data-model.md, and the SSE frame parser that satisfies T045.
- [x] T053 [US6] Implement the client operations in `src/loopplane/cli/remote.py`: open (`POST /v1/sessions`), attach (use the supplied id), submit (`POST /v1/sessions/{id}/submit`), answer approval and question, cancel, list sessions, and forward a command (`POST /v1/commands`) — each sending the bearer credential and each mapping a non-2xx response to a public-safe failure that never echoes the credential.
- [x] T054 [US6] Implement the remote interactive loop in `src/loopplane/cli/remote.py`, reusing `prompts.py` for input and `EventRenderer` for output, and dispatching commands through the shared registry with `CommandContext(remote=True)` before deciding whether to forward.
- [x] T055 [US6] Add the `remote` subcommand to `src/loopplane/cli/app.py` with `--url`, `--token` (falling back to `LOOPPLANE_TOKEN`), and `--session`, returning exit code 2 for usage errors and 1 for connection failures.
- [x] T056 [US6] Re-export the new public core from `src/loopplane/cli/__init__.py` in the same style as the existing exports.

**Checkpoint**: the terminal drives a remote agent; only resilience remains.

---

## Phase 9: User Story 7 — Survive a dropped connection (Priority: P3)

**Goal**: a dropped remote stream reconnects on its own and resumes exactly where it left off.

**Independent Test**: force a stream break mid-turn and assert the rendered event sequence has
no duplicate and no gap across the break.

### Tests for User Story 7

- [x] T057 [P] [US7] Write a failing integration test in `tests/integration/test_cli_remote.py` that breaks the event stream mid-turn and asserts the client reconnects with the correct `Last-Event-ID` and that the full rendered sequence contains neither a duplicate nor a gap.
- [x] T058 [P] [US7] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting the operator sees a reconnection indication rather than silence.
- [x] T059 [P] [US7] Write a failing integration test in `tests/integration/test_cli_remote.py` asserting that a `404` on reconnect (session ended or not resumable) produces a public-safe explanation and a clean exit from that conversation.
- [x] T060 [P] [US7] Write a failing unit test in `tests/unit/test_cli_remote_stream.py` asserting reconnection attempts are bounded and that exhaustion stops retrying, reports, and returns control.

### Implementation for User Story 7

- [x] T061 [US7] Implement reconnection in `src/loopplane/cli/remote.py`: on a dropped stream, re-issue the events request with `Last-Event-ID` set to the cursor, reset the attempt counter on any received frame, and cap attempts.
- [x] T062 [US7] Render the reconnection state and the terminal outcomes (`[reconnecting…]`, exhausted, no longer resumable) in `src/loopplane/cli/remote.py`, all public-safe.

**Checkpoint**: every user story is complete and independently testable.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [x] T063 [P] Update `docs/cli.md`: the new `chat` semantics (one continuing conversation), interactive `resume`, the `remote` subcommand and its options, the interrupt meanings, the approval/question input grammar, and the full command list with remote-safety.
- [x] T064 [P] Update `docs/api-reference.md`: add `CommandDescriptor` to the `loopplane.commands` section, note `register`'s new keyword arguments, `describe()`, `CommandContext.remote`, and the four new commands; extend the `loopplane.cli` section with the new public core.
- [x] T065 Write a contract test in `tests/contract/test_cli_public_safety.py` that runs a local turn and a remote turn with `LOOPPLANE_SECRET_MARKER` as the credential and synthetic path/rule/PID markers in the environment, asserting via `tests/helpers/public_safety.py` that no prohibited marker appears in any rendered output, failure message, or diagnostic. Keep marker assertions on single-line probes.
- [x] T066 Extend `tests/integration/test_cli_boundary.py` so the import fence covers `src/loopplane/cli/remote.py` and `src/loopplane/cli/prompts.py`: no gateway internals, no `loopplane.tools`, no runtime-internal module, and `httpx` not imported at module import time.
- [x] T067 Verify the byte-identity claims: `tests/integration/test_webapi_commands.py` and `tests/unit/test_desktop_command_methods.py` pass unedited. Add a cross-surface equality test in `tests/unit/test_commands.py` (SC-005) asserting that one registry dispatching the same command line under a CLI-shaped context and a web-shaped context returns identical `kind` and `text`.
- [x] T068 Run the gates in order and record the literal results: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest -q`. Re-run any known flake (`tests/integration/test_examples_smoke.py`, `test_us2_mcp`) in isolation before drawing a conclusion.
- [x] T069 Walk `specs/079-cli-remote-parity/quickstart.md` scenarios 1, 3, 4, and 6 by hand against the built CLI and record the observed output. Scenarios 2 and 5 are covered by the integration suites where a live server is unavailable. *(Ran `loopplane --help` — `remote` listed; `loopplane run` — one-shot unchanged; `loopplane chat` — one continuing conversation, `/help` listing all eight commands, `/history` shape-only, `/compact` effective; `loopplane remote` with nothing supplied — usage line, exit 2, nothing echoed; `loopplane remote --url` at a closed port — `could not reach the server`, exit 1.)*
- [x] T070 Update `docs/loopplane-agent-board.md`: set the 079 row's status and Next Action, and refresh §4 "Active Feature", which still names 083. **Do not** hand-edit the `<!-- SPECKIT START/END -->` blocks in `AGENTS.md` or `CLAUDE.md`; report the agent-context tool's failure in this environment instead.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies; T001 must land before any US6 acceptance test is written.
- **Foundational (Phase 2)**: depends on Setup; **blocks every user story** because all of them read input through `prompts.py`.
- **US1 (Phase 3)**: depends on Foundational. Blocks US2 and US3 — both act on the open conversation US1 introduces.
- **US2 (Phase 4)** and **US3 (Phase 5)**: depend on US1; independent of each other.
- **US4 (Phase 6)**: depends on Foundational only. Can proceed in parallel with US1–US3.
- **US5 (Phase 7)**: depends on US4 (it classifies the commands US4 registers).
- **US6 (Phase 8)**: depends on Foundational, US2 (approval/question handling is reused), and US5 (the remote policy it enforces).
- **US7 (Phase 9)**: depends on US6.
- **Polish (Phase 10)**: depends on every story that ships.

### Parallel opportunities

- Phase 2's T003/T005 are sequential (same file); T007 is independent.
- All `[P]` test tasks within one story touch different files or different test functions and can be written together.
- US4 (Phase 6) is fully independent of US1–US3 and can run alongside them.
- Phase 10's T063 and T064 are different documents and parallelize.

### Within each story

- The failing test comes first and must actually fail for the intended reason.
- Shapes (dataclasses, protocols) before handlers; handlers before wiring; wiring before the CLI entry point.
- A story is not done until its checkpoint's independent test passes.

---

## Parallel Example: User Story 6

```text
# Write the failing tests together:
T045 SSE frame parsing            -> tests/unit/test_cli_remote_stream.py
T046 open + submit + render       -> tests/integration/test_cli_remote.py
T047 remote approval and question -> tests/integration/test_cli_remote.py
T049 non-disclosure on attach     -> tests/integration/test_cli_remote.py
T051 failure surfaces             -> tests/unit/test_cli_remote_stream.py
```

---

## Implementation Strategy

### MVP

Phase 1 → Phase 2 → Phase 3 (US1). At that point the terminal holds a real conversation,
which is the single largest gap this unit closes. Stop and validate before continuing.

### Incremental delivery

1. Setup + Foundational → one input abstraction, one-shot path pinned.
2. US1 → a conversation that remembers. **MVP.**
3. US2 + US3 → the terminal can supervise and stop a gated agent. P1 complete.
4. US4 + US5 → a richer command surface plus the policy the remote path needs.
5. US6 → remote operation.
6. US7 → remote resilience.
7. Polish → docs, public-safety contract, boundary fence, gates, board.

Each step leaves the tree green and every earlier story working.

---

## Notes

- `[P]` means different files and no dependency on an incomplete task.
- Verify each test fails for the intended reason before implementing against it.
- Stop at any checkpoint to validate the story on its own.
- If any task appears to require an event/record schema change, a gateway SPI change, a
  default change, or an outward web contract change, stop and ask — that is a §E gate, not a
  judgement call.

---

## Phase 11: Post-review remediation (2026-08-21)

A two-reviewer pass (code + architecture) after Phase 10 found three blocking defects that all
four green gates had missed, because every test used instant scripted turns and list-driven
input. All are fixed; each fix carries a test that fails without it.

- [x] T071 **B1 — cross-principal disclosure.** `webapi/app.py`'s ownership gate covered only a hardcoded `("cost", "compact")`, so 079's `/history` and `/permission` were reachable through `POST /v1/commands` without an ownership check. Fixed at the root: `CommandRegistry` now declares `session_scoped` per command and the route reads `session_scoped_names()`, so the gate cannot fall out of step with the command set (FR-041).
- [x] T072 **B1, second layer.** `_readable_session` in `src/loopplane/commands/__init__.py` makes `/history` and `/permission` refuse a conversation the caller does not own, so a host that omits its gate degrades to "not found" rather than leaking (FR-042).
- [x] T073 **B1 tests.** Cross-principal, non-disclosure, and registry-coupling tests in `tests/integration/test_webapi_commands.py`; second-layer tests in `tests/unit/test_commands.py`. **Negative self-check run**: with the gate regressed to the pre-fix list, five of the new tests fail; restored, all pass.
- [x] T074 **B2 — the interrupt branch was unreachable.** A real Ctrl-C under `anyio.run` cancels the task, so `CancelledError` reaches the await and `except KeyboardInterrupt` never fires outside tests. Verified experimentally, then fixed with `interrupt_watch` in `src/loopplane/cli/prompts.py`, which installs a SIGINT handler and asks the runtime to cancel (FR-043). *(Scope corrected in T088: the handler is installed per turn, not for the life of the conversation.)*
- [x] T075 **B2 tests.** `tests/integration/test_cli_interactive.py` now drives interruption with a **real** `signal.raise_signal(SIGINT)`; `tests/unit/test_cli_prompts.py` keeps the runner-behavior experiment as a subprocess regression test, so the design's premise stays executable.
- [x] T076 **B3 — a 30-second client timeout ended any realistic remote turn.** `/submit` spans the whole turn server-side. The client now leaves reads unbounded while keeping connect/write/pool bounded (FR-032), with a slow-turn test against the real app and a test pinning the intent.
- [x] T077 **M1 — non-JSON success bodies.** `RemoteClient._body` normalizes any parse failure to the fixed public-safe message, so a proxy interstitial cannot escape as a raw error.
- [x] T078 **M2 — a failed answer POST silently lost the request.** The stream cursor now advances only after a frame is fully handled, so a failed approval answer is replayed on reconnect and asked again instead of parking the turn forever.
- [x] T079 **M3 — one blocking line source shared by two tasks.** `LineSource.anext_line` reads off the event loop and serializes concurrent readers, so the stream keeps rendering while the operator thinks.
- [x] T080 **The settle wait could cost a full timeout.** A terminal frame arriving before `submit` returned was lost by the per-turn Event; replaced with a counter, and the wait now watches the stream giving up as well (this alone took the remote suite from 82s to 2.4s).
- [x] T081 **FR-022 on the remote path.** `/help` is answered locally from the shared `format_command_listing`, so the listing matches the operator's context instead of the server's.
- [x] T082 **Reconnection backoff** (FR-037), plus attempts no longer reset on an unreadable frame — together these stop a busy spin that starved the event loop.
- [x] T083 **Minor fixes**: `api_prefix` is overridable on `RemoteEndpoint`; a gone conversation exits 1 however it is discovered; `parse_frame` drops only the SSE separator space instead of all leading whitespace.
- [x] T084 **Boundary record.** `TARGET_ARCHITECTURE_BOUNDARIES.md` Block 2 (optional dependency) and Block 3 (the CLI as a third contract consumer) corrected; **ADR 0018** drafted for the maintainer, who accepted it on 2026-08-21.
- [x] T085 **Gates re-run**: ruff format + check, mypy, and the full suite green.

---

## Phase 12: Second remediation round (2026-08-21)

The Phase 11 fixes were themselves reviewed, and the review found that two of them had made
things worse. Recorded here because the lesson generalizes: a fix for an unreachable path is
untested by construction until the path is made reachable, and B2 and B3 interacted — removing
the read deadline meant a wedged turn now hung forever, exactly when the interrupt that was
supposed to rescue it had just been rerouted.

- [x] T086 **B2 regression — the remote interrupt could not preempt a blocked submit.** `interrupt_watch` asked the client to cancel, but the terminal was parked in `await client.submit(...)`, which after T076 no longer times out. `_submit_racing_interrupt` in `src/loopplane/cli/remote.py` now races the submit against the interrupt event, so Ctrl-C returns the operator to the prompt while the cancel POST is in flight.
- [x] T087 **My own fix swallowed the cancellation.** The racing task first caught `BaseException`, which absorbed the `CancelledError` that ends the turn and reported it as a failure. Narrowed to `except (Exception, KeyboardInterrupt)`, with a comment saying why the broad form is wrong here.
- [x] T088 **The interrupt watch was conversation-scoped, and that was unsafe.** A SIGINT arriving while the operator was idle at the prompt set a flag that the *next* turn consumed, and a handler that re-raised `KeyboardInterrupt` landed at an uncontrollable point (it killed the pytest process). The watch is now installed per turn and removed with it; the idle window is handled by `dispatch`'s `except KeyboardInterrupt`, which exits cleanly. `InterruptState.take()` makes a stale flag impossible to carry across turns.
- [x] T089 **Interrupting did not cancel the following turn.** After a turn ends, the controller re-arms a fresh one-shot cancel signal, so calling `session.cancel()` from the post-turn interrupt branch armed the *next* turn instead. The branch now only reports.
- [x] T090 **Teardown could hang on the input thread.** `LineSource.anext_line` waits on a thread blocked in `input()`, which returns only when the operator types. It now uses `abandon_on_cancel=True`, so shutdown is not hostage to a keystroke.
- [x] T091 **F1 (architecture) — the defense was described as universal but was not.** `/compact` and `/cost` predate this unit and had no handler-level ownership check, while ADR 0018 D3 claimed every session-scoped handler had one. All four now call `_readable_session`, a test pins the coupling, and D3 records why the two ownership predicates deliberately differ (a principal-less session is nobody's to the web host, and one's own to a host without principals).
- [x] T092 **F2 (architecture) — FR-034's no-loss guarantee is server-conditional.** Replay depends on the server having an `EventReplayStore`; against one without it, a resume can only pick up live. The spec now carries that as an Assumption, and `RECONNECTING_UNSEQUENCED_NOTICE` says so in the terminal instead of leaving the operator to infer it.
- [x] T093 **Exit code no longer races the loop.** Whether a gone conversation was discovered by the stream or by a POST, the exit-1 decision is made once, after the loop.
- [x] T094 **Records synchronized**: `docs/api-reference.md` (`api_prefix`), `TARGET_ARCHITECTURE_BOUNDARIES.md` Block 2 public API, the board's test count, and ADR 0018 D3.
- [x] T095 **Gates re-run after round 2**: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest -q` → **2195 passed, 33 skipped**. `apps/` untouched, so the six-registry discipline never applied; no unit-082 file was read, staged, or modified.
