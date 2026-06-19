# Tasks: Model-Native Structured Output

**Feature**: 045-structured-output | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive. Touches `model/boundary.py`, `model/capabilities.py`, the OpenAI mapping
+ adapter configs, the web/API edge, and tests. No `stream_turn` signature change, no
event-schema/content-model change, no new dependency, no ADR. v1 maps the OpenAI-family;
Anthropic/Gemini native structured output deferred (capability flag `False`).

**Tests**: requested (TDD-friendly ordering).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add an optional `output_schema: dict[str, object] | None = None` field to `ModelRequest` in `src/loopplane/model/boundary.py` (additive; default `None` = byte-identical).
- [ ] T002 Add a `StructuredOutputModel` Protocol + `supports_structured_output(model) -> bool` probe to `src/loopplane/model/capabilities.py`, mirroring `accepts_media` (advertised value, else conservative `False`).

## Phase 2: User Story 1 — Constrain a response on a supporting provider (P1) 🎯 MVP

**Goal**: a supplied schema configures the provider request on the OpenAI-family.

**Independent test**: build a `ModelRequest` with `output_schema` and drive the OpenAI mapping; the request carries `response_format` json_schema; `None` → no `response_format`.

- [ ] T003 [US1] In the OpenAI chat-completions mapping (`src/loopplane/adapters/openai/mapping.py`), when `request.output_schema` is set, add `response_format = {"type": "json_schema", "json_schema": {"name": ..., "schema": output_schema, "strict": True}}`; when `None`, emit no `response_format` (byte-identical).
- [ ] T004 [US1] Add a `supports_structured_output` config flag (default `True`) + a `supports_structured_output()` method on the OpenAI adapter (`src/loopplane/adapters/openai/adapter.py`).
- [ ] T005 [US1] Set capability flags on the other adapters: `openrouter_model` = `True`, `ollama_model` = configurable (default `False`) in `src/loopplane/adapters/openai_compat/`; `anthropic` = `False` and `gemini` = `False` (deferred — graceful degradation).
- [ ] T006 [US1] Thread an optional `RunRequest.output_schema` (web/API) into `ModelRequest.output_schema` on the run path (`src/loopplane/webapi/`), mirroring how unit-036 threads uploads.
- [ ] T007 [P] [US1] Write `tests/unit/test_structured_output.py`: OpenAI mapping sets `response_format` when a schema is present and omits it when `None` (byte-identical off-path).

## Phase 3: User Story 2 — Graceful degradation + catalog (P2)

**Goal**: a schema for a non-supporting model is rejected clearly; the catalog advertises the capability.

**Independent test**: POST a run with a schema to a non-supporting model → HTTP 400; `/v1/models` reports the flag.

- [ ] T008 [US2] In the web/API model-selecting boundary, reject a run that supplies a schema to a model whose `supports_structured_output(model)` is `False` with a clear normalized HTTP 400 (no run started); reject a malformed schema with HTTP 400 at request time (before any model call).
- [ ] T009 [US2] `/v1/models` (the catalog) advertises `supports_structured_output` per model.
- [ ] T010 [P] [US2] Extend `tests/unit/test_structured_output.py`: `supports_structured_output(model)` probe (advertised + non-advertising → False); web/API rejection (non-supporting model + malformed schema); catalog advertises the flag.

## Phase 4: User Story 3 — Verifiable against the schema (P3)

- [ ] T011 [US3] Test: a structured response validates against its schema via the existing unit-005 JSON-schema validator pack (conforming passes; non-conforming fails with a diagnostic).

## Phase 5: Polish & Cross-Cutting

- [ ] T012 If `supports_structured_output` becomes a public/exported name (as `accepts_media` is), update the unit-014 API reference (and any `__all__`) so the api-reference bijection test stays green; mirror exactly how `accepts_media` is exported/documented. If it is not exported, note that and skip.
- [ ] T013 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict), `pytest` (full suite — additive proof). Fix any issue introduced by this unit.

## Dependencies

- T001, T002 → block all of Phase 2+.
- T003–T006 → T007 (US1 tests). T002/T006 → T008, T009 → T010. T011 after the handler/mapping.
- T012 → T013 (gates last).

## Parallel opportunities

- T007 and T010 extend the same test file → sequential. T003 (mapping) and T006 (webapi) are
  different files and can proceed in parallel after T001/T002.

## Implementation strategy

- **MVP = Phase 1 + Phase 2 (US1)**: a supplied schema constrains an OpenAI-family request
  end-to-end with the off-path proven byte-identical. US2 adds the negotiation/rejection and
  catalog; US3 adds the validation proof.
- All changes additive; default `None` path byte-identical. Anthropic/Gemini native mapping is
  a documented follow-up.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
