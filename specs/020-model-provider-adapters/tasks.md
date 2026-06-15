---
description: "Task list for unit 020 — Real Model-Provider Adapters"
---

# Tasks: Real Model-Provider Adapters

**Input**: Design documents from `specs/020-model-provider-adapters/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Offline mapping + integration tests run in the
`pytest` gate with a **stub client** (no SDK network, no credential). The one **live**
test is opt-in and excluded from CI. Write each test FIRST and confirm it FAILS first.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (extras + dev SDKs)

- [ ] T001 `pyproject.toml`: add optional extras `anthropic = ["anthropic>=..."]` and
  `openai = ["openai>=..."]`; add both SDKs to the `dev` dependency-group (for
  `mypy --strict` and tests). Runtime dependency set stays `anyio + pydantic + jsonschema`.
- [ ] T002 Update `tests/contract/test_packaging.py::test_runtime_dependencies_are_unchanged`:
  the pinned optional-dependencies set becomes `{anthropic, mcp, openai, otel, web}`
  (runtime-deps assertion unchanged). Run `uv sync`.

---

## Phase 2: Foundational

No shared runtime code: each adapter is self-contained under its own package (keeps each
importable without the other's SDK and avoids a shared public name). Proceed to the stories.

---

## Phase 3: User Story 1 — drive a real run with a real model (P1) 🎯 MVP

**Goal**: both adapters map a real turn (text + tool-use round-trip) through the loop.

**Independent Test**: a stub client drives `AgentLoop`; a text turn streams `TextIncrement`s
+ `TurnEnd`, and a tool-use turn completes the gateway round-trip — parametrized over both.

- [ ] T003 [P] [US1] `tests/unit/test_anthropic_mapping.py` (FAIL first): request mapping
  (`ContentBlock`/`ToolDescriptor` → Anthropic message/tool shapes per data-model.md) and
  event mapping (stand-in `text_delta` / `tool_use` block + `input_json_delta` /
  `message_delta` → `TextIncrement` / `ToolCallRequest` / `TurnEnd`).
- [ ] T004 [P] [US1] `tests/unit/test_openai_mapping.py` (FAIL first): request mapping
  (→ OpenAI role/tool shapes) and chunk mapping (stand-in `delta.content` /
  `delta.tool_calls` deltas + `finish_reason` → increments).
- [ ] T005 [US1] Implement `src/loopplane/adapters/anthropic/`: `config.py`
  (`AnthropicConfig` + lazy default client factory), `mapping.py` (duck-typed mapping),
  `adapter.py` (`AnthropicModel(ModelBoundary)` — `stream_turn` async generator ending in
  one `TurnEnd`; `context_capacity`), `__init__.py` (`__all__ = AnthropicModel, AnthropicConfig`).
- [ ] T006 [US1] Implement `src/loopplane/adapters/openai/` (same four-file shape:
  `OpenAIConfig`, `mapping.py`, `OpenAIModel`, `__init__.py`).
- [ ] T007 [US1] `tests/integration/test_us1_model_providers.py` (FAIL first → pass):
  parametrized over both adapters with a stub client through `LoopPlaneHost`/`AgentLoop` —
  (a) text turn streams text then ends; (b) tool-use turn → gateway executes an internal
  tool → result fed back → model continues to end-turn (FR-001/FR-002/FR-003, SC-002).

**Checkpoint**: both adapters drive a real loop offline; the suite is green.

---

## Phase 4: User Story 2 — context-overflow compaction (P2)

**Goal**: both adapters raise `ContextOverflowError` so the loop compacts and retries once.

- [ ] T008 [US2] `tests/integration/test_us2_model_overflow.py` (FAIL first): a stub client
  signals "context too long"; assert each adapter raises `ContextOverflowError` and, with
  an assembler attached, the loop compacts and retries exactly once (FR-004).
- [ ] T009 [US2] Implement overflow detection in both adapters' `mapping.py`/`adapter.py`
  (map the provider's length error → `ContextOverflowError`).

---

## Phase 5: User Story 3 — public-safe failures + usage (P3)

**Goal**: provider/transport faults are public-safe; token usage is reported.

- [ ] T010 [US3] `tests/integration/test_us3_model_failures.py` (FAIL first): a stub client
  raises a transport/4xx error carrying a secret-looking string → the run terminates
  `unrecoverable-error`, the adapter's exception message contains no credential/body, and a
  successful turn maps usage into `TurnEnd.usage` (FR-005/FR-007, SC-003).
- [ ] T011 [US3] Implement public-safe error re-raise (fresh message, no key/body) and the
  usage mapping (per data-model.md) in both adapters.

---

## Phase 6: Polish — packaging, docs, live, gate

- [ ] T012 [P] `docs/api-reference.md`: add the `loopplane.adapters.anthropic` and
  `loopplane.adapters.openai` sections, each listing exactly that package's `__all__`
  (api-reference drift contract).
- [ ] T013 [P] `docs/model-providers.md` (the guide) + link it in `docs/README.md`
  (docs-index contract).
- [ ] T014 [P] `examples/anthropic_quickstart.py` + `examples/openai_quickstart.py`
  (lazy SDK import; env-injected key; clean no-key exit) + list both in
  `examples/README.md` (examples-index contract).
- [ ] T015 [P] `CHANGELOG.md`: add a `020` entry under Added (Keep-a-Changelog structure).
- [ ] T016 `tests/live/test_live_models.py`: opt-in, `skipif` on the absence of the
  provider API-key env var; one real text turn per provider. Excluded from CI (no
  `secrets.` in `ci.yml`).
- [ ] T017 Run the gates: `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy`, `uv run pytest` — all green; `uv build` succeeds. Confirm
  `import loopplane.adapters.anthropic` / `...openai` works without the SDKs installed
  (lazy-import invariant) and the public-safety scan is clean.
- [ ] T018 Final review: record unit 020 in `docs/loopplane-agent-board.md`; commit
  (`020 implement`).

---

## Dependencies & Execution Order

- Phase 1 (extras/dev SDKs) precedes everything (mypy/tests need the SDKs installed).
- US1 (T003–T007) is the MVP. US2 and US3 extend the same two adapters and depend on
  US1's adapter files existing. Phase 6 wiring depends on the `__all__` from T005/T006.

### Parallel opportunities

- T003/T004 (per-provider mapping tests) run in parallel; T005/T006 (the two adapters)
  touch disjoint packages and can be written in parallel.
- T012–T015 (docs/examples/changelog) are independent `[P]` files.

## Notes

- The adapters implement the **existing** `ModelBoundary`; nothing in the runtime core
  changes (Constitution VIII). Tool calls surface as raw `ToolCallRequest` for the
  gateway (V); only normalized increments reach the loop (VI).
- Each adapter imports its SDK **lazily**, so both packages import without the SDK
  (packaging import contract). Credentials are injected, never committed (VII).
- Rollback = delete the two adapter packages, their tests/examples/guide, and revert the
  additive `pyproject`/api-reference/index/changelog/packaging-test edits.
