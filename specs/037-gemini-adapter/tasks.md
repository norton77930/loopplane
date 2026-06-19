---
description: "Task list for Native Google Gemini Adapter (spec 037)"
---

# Tasks: Native Google Gemini Model-Provider Adapter

**Input**: Design documents from `/specs/037-gemini-adapter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/model-provider-adapter.md, contracts/integration-boundary.md

**Tests**: REQUIRED (Constitution X) — offline, deterministic. Write tests FIRST and
confirm they FAIL before implementing each piece.

**Organization**: by user story (US1 text/stream P1, US2 tool use P1, US3 vision
P2). All stories share one new package + one unit-test module, so implementation is
a single cohesive native adapter mirroring unit 020.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

## Phase 1: Setup

- [ ] T001 Add the optional extra `gemini = ["google-genai>=1"]` to `pyproject.toml` `[project.optional-dependencies]`, and add `google-genai>=1` to the `dev` dependency group; run `uv lock` / `uv sync` so `uv run` resolves (report any `uv.lock` change; if the wheel cannot resolve offline, keep the extra declared + the import lazy and rely on the offline stub tests, per research Decision 2).

## Phase 2: Foundational

- [ ] T002 Create the package skeleton `src/loopplane/adapters/gemini/__init__.py` (re-export `GeminiConfig`, `GeminiModel`; declare `__all__ = ["GeminiConfig", "GeminiModel"]`) — so the package imports without the SDK (the import-boundary contract).
- [ ] T003 Create `src/loopplane/adapters/gemini/config.py`: `GeminiConfig` (frozen dataclass: `model`, `context_capacity=1_000_000`, `max_output_tokens=None`, `api_key=None`, `client=None`, `client_factory=default_client_factory`, `accepts_media=True`) + `default_client_factory(api_key)` importing `from google import genai` **lazily** and returning `genai.Client(api_key=...)` (or `genai.Client()`).

## Phase 3: User Story 1 — Text + streaming + usage (P1)

**Goal**: `stream_turn` yields ordered `TextIncrement`s → one `TurnEnd` with the
mapped `TokenUsage`, against a Gemini-shaped stub stream.

**Independent Test**: drive `GeminiStreamDecoder` with text parts + a
`usage_metadata` chunk and assert `[TextIncrement, …, TurnEnd]` with the mapped
usage.

- [ ] T004 [P] [US1] Tests (write first, must FAIL): in `tests/unit/test_gemini_mapping.py`, decode a stub stream of text parts + a `usage_metadata` chunk → `TextIncrement`(s) then one `TurnEnd` carrying `prompt_token_count`/`candidates_token_count`/cached/thoughts; assert `build_contents` maps a `TextBlock` user message to `{"role":"user","parts":[{"text":...}]}`.
- [ ] T005 [US1] Implement `build_contents` (text + summary-marker parts; roles user/model) and the `GeminiStreamDecoder` text + `usage_metadata` + `finish_reason` → `TurnEnd` path in `src/loopplane/adapters/gemini/mapping.py`.
- [ ] T006 [US1] Implement `GeminiModel` in `src/loopplane/adapters/gemini/adapter.py`: build the client (injected or via factory); `context_capacity`; `accepts_media`; `stream_turn` calling `client.aio.models.generate_content_stream(...)`, feeding the decoder, ending with one `TurnEnd`.

**Checkpoint**: a text turn streams end-to-end against the stub client.

## Phase 4: User Story 2 — Tool use (raw `ToolCallRequest`) + multi-turn (P1)

**Goal**: a `function_call` part → a raw `ToolCallRequest`; a re-mapped prior
`ToolCallBlock`/`ToolResultBlock` builds `function_call`/`function_response` parts
with the `skip_thought_signature_validator` sentinel.

**Independent Test**: decode a `function_call` stub stream → one `ToolCallRequest`
(raw args) + one `TurnEnd`; assert `build_contents` + `build_tools` for a tool round
trip.

- [ ] T007 [P] [US2] Tests (write first, must FAIL): decode a `function_call` part (name + args) → one `ToolCallRequest` with raw args + one `TurnEnd`; `build_tools([ToolDescriptor])` → `[{"function_declarations":[{"name","description","parameters"}]}]`; `build_contents` for a prior `ToolCallBlock` (role `model`, a `function_call` part carrying `thought_signature == "skip_thought_signature_validator"`) + a `ToolResultBlock` (role `user`, a `function_response` part); assert the sentinel is on the part, **not** in `args`.
- [ ] T008 [US2] Implement `build_tools`, the `function_call`/`function_response` mapping in `build_contents` (with the `SKIP_THOUGHT_SIGNATURE` sentinel on a re-mapped `function_call`), and the decoder's `function_call` accumulation → raw `ToolCallRequest` (synthesized stable `call_<n>` id) in `mapping.py`; wire `tools` into `stream_turn`'s `GenerateContentConfig`.

**Checkpoint**: single-turn and multi-turn tool use map correctly (no 400 on a
missing signature).

## Phase 5: User Story 3 — Vision + reasoning + capability (P2)

**Goal**: an `ImageBlock` → an `inline_data` part; a thought part →
`ReasoningIncrement`; `accepts_media() == True`.

**Independent Test**: `build_contents` for an `ImageBlock` → an `inline_data` part;
decode a thought part → `ReasoningIncrement`; probe `accepts_media`.

- [ ] T009 [P] [US3] Tests (write first, must FAIL): `build_contents` maps `ImageBlock(media, format)` → a part `{"inline_data":{"mime_type":format,"data":media}}`; the decoder maps a part with `.thought is True` → `ReasoningIncrement`; `GeminiModel(GeminiConfig(model="g", client=object())).accepts_media()` is `True` and `accepts_media(model)` is `True`, and `accepts_media=False` flips it.
- [ ] T010 [US3] Implement the `ImageBlock` → `inline_data` mapping in `build_contents` and the thought-part → `ReasoningIncrement` branch in the decoder.

## Phase 6: Polish & Cross-Cutting

- [ ] T011 [P] Add a Gemini-shaped stub client + chunk builder to `tests/integration/provider_stubs.py` and add `"gemini"` to `PROVIDERS` + `make_model` / `make_failing_model` / `overflow_error`, so the existing parametrized US2 overflow + US3 failure/usage suites also exercise the Gemini adapter (verify they pass).
- [ ] T012 [US2/US1] Implement error normalization in `adapter.py`: a `_translate_error` reusing `loopplane.adapters._model_errors` — a context-overflow signal (400/`INVALID_ARGUMENT` naming the token/context limit, or 429/`RESOURCE_EXHAUSTED`) → `ContextOverflowError`; any other fault → `ModelProviderError` (public-safe; no key/raw-body leak). Add the overflow + non-leak assertions (covered via the parametrized integration suites from T011).
- [ ] T013 [P] Extend `tests/unit/test_capabilities.py` with a `test_gemini_adapter_accepts_media_by_default` (default `True`; `accepts_media=False` flips it) — mirroring the Anthropic/OpenAI cases.
- [ ] T014 [P] Add an opt-in, secret-gated Gemini live turn to `tests/live/test_live_models.py` (`skipif` on `GEMINI_API_KEY` + `LOOPPLANE_GEMINI_MODEL`; excluded from CI) and extend `docs/real-model-validation.md` with the Gemini env vars.
- [ ] T015 Add the `### \`loopplane.adapters.gemini\`` section to `docs/api-reference.md` (2 names = the package `__all__`: `GeminiConfig`, `GeminiModel`) so the unit-014 bijection stays green.
- [ ] T016 Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green (the prior 846 passed + the new tests).
- [ ] T017 Update tracking: `CHANGELOG.md` (a `**037**` entry after `**036**`), `docs/loopplane-agent-board.md` (§3 row after 036 + §4 Active Feature pointer + the §4 deferred-items note), `.specify/feature.json` (→ `specs\037-gemini-adapter`), and the `CLAUDE.md` SPECKIT pointer (→ `specs/037-gemini-adapter/plan.md`).

## Dependencies & Execution Order

- T001 → T002 → T003 → (US1 T004/T005/T006) → (US2 T007/T008) → (US3 T009/T010) → T011 → T012 → (T013/T014/T015 [P]) → T016 → T017.
- US1/US2/US3 share the package + the unit-test module, so they land together as one cohesive adapter (like unit 020).

## Parallel Opportunities

- T004, T007, T009 (the per-story test files write to one new module but distinct test functions) and T011, T013, T014 (distinct test files) are `[P]`-marked where they touch disjoint files.

## Notes

- New optional extra `gemini` (`google-genai`), imported lazily; **no required**
  runtime dependency; the package imports without the extra.
- **The content model and the event schema are UNCHANGED** — no `ToolCallBlock`
  field, no `SCHEMA_VERSION` bump, **no ADR** (the conservative `thought_signature`
  path uses Google's official sentinel; research Decision 3).
- Tool calls surface as **raw** `ToolCallRequest`s; the gateway validates (V). Only
  normalized increments reach the loop (VI). The SDK enters only as a model-boundary
  adapter (VIII).
- Do NOT commit/push during this unit (the parent reviews — especially the
  content-model / event-schema decision — then commits).
- Rollback = delete the package + the unit-test module + the Gemini stub/capability/
  live entries + the `gemini` extra + the api-reference section; units 020/035/036,
  the content model, and the event schema are untouched.
