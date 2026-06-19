---
description: "Task list for OpenAI-Compatible Model Providers (spec 035)"
---

# Tasks: OpenAI-Compatible Model Providers (OpenRouter + Ollama)

**Input**: Design documents from `/specs/035-openai-compatible-providers/`

**Tests**: REQUIRED (Constitution X) — offline, deterministic.

**Organization**: by user story (US1 OpenRouter P1, US2 Ollama P2). Both share
one new package + one test module, so implementation is a single cohesive change.

## Phase 1: Setup

- [x] T001 Create the offline test harness in `tests/unit/test_openai_compat.py`: a fake `openai` module (recording `AsyncOpenAI` kwargs) installed via `monkeypatch.setitem(sys.modules, "openai", ...)`.

## Phase 2: Foundational

- [x] T002 Create the `src/loopplane/adapters/openai_compat/__init__.py` package: a `_base_url_client_factory(base_url)` closure (lazy `openai` import) reused by both constructors; `OPENROUTER_BASE_URL` / `OLLAMA_BASE_URL`; and `__all__`.

## Phase 3: User Story 1 — OpenRouter (P1)

- [x] T003 [US1] Tests (write first): OpenRouter passes its base_url + injected key to the client; `openrouter_model(..., client=obj)` returns an `OpenAIModel` (reuse).
- [x] T004 [US1] Implement `openrouter_model(...)` in the package, building an `OpenAIModel` with the OpenRouter base_url factory.

## Phase 4: User Story 2 — Ollama (P2)

- [x] T005 [US2] Tests (write first): Ollama uses the local base_url + placeholder key; a custom base_url is honored; returns an `OpenAIModel`.
- [x] T006 [US2] Implement `ollama_model(...)` in the package (placeholder key, overridable base_url).

## Phase 5: Polish & Cross-Cutting

- [x] T007 Add the `### loopplane.adapters.openai_compat` section to `docs/api-reference.md` (4 names = the package `__all__`) so the unit-014 bijection stays green.
- [ ] T008 Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green.
- [ ] T009 Update `CHANGELOG.md` (a `**035**` entry) + `docs/loopplane-agent-board.md` (§3 row + §4 → native Gemini / 036 next) + `.specify/feature.json` + `CLAUDE.md` SPECKIT pointer.

## Dependencies & Execution Order

- T001 → T002 → (US1 T003/T004) → (US2 T005/T006) → T007 → T008 → T009.
- US1 and US2 share the package/test module, so they land together.

## Notes

- No new dependency (rides the existing `openai` extra); no frontend; no ADR.
- Native Gemini is OUT OF SCOPE (deferred follow-up; reachable via OpenRouter).
- Rollback = delete the package + test module + the api-reference section.
