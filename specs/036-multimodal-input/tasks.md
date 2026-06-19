---
description: "Task list for Multimodal Input (spec 036)"
---

# Tasks: Multimodal Input (Image Attachments to the Model)

**Input**: Design documents from `/specs/036-multimodal-input/` + the ADR
`docs/adr/0001-multimodal-content.md`.

**Tests**: REQUIRED (Constitution X) — offline, deterministic. Write failing tests
first where practical.

**Organization**: by user story (US1 image input P1, US2 graceful degradation P1).
The model-boundary probe (foundational) is shared by both.

## Phase 1: ADR + Spec docs (gating, Constitution I/IV/VI)

- [x] T001 Write the narrowed ADR `docs/adr/0001-multimodal-content.md` (Status / Context / Decision D1–D6 / Consequences / Alternatives): image input ships with NO content-model or event-schema change; PDF deferred (no base64 PDF in OpenAI chat-completions); binary durability + gateway non-text handoff deferred; duck-typed `accepts_media` + web-edge degradation; media size cap.
- [x] T002 Write the spec-kit doc set under `specs/036-multimodal-input/`: `spec.md`, `checklists/requirements.md`, `plan.md` (Constitution Check; reference the ADR), `research.md`, `data-model.md`, `contracts/multimodal.md`, `quickstart.md`, `tasks.md`.

## Phase 2: Foundational — model-boundary capability probe (US1 + US2 share it)

- [ ] T003 Tests (write first) in `tests/unit/test_capabilities.py`: `accepts_media(model)` returns `True`/`False` for a stub that implements `accepts_media()`, `False` for a stub that does not (and for `ScriptedModel`); the adapters report their config flag (Anthropic/OpenAI default `True`; `openrouter_model` default `True`, `ollama_model` default `False`).
- [ ] T004 Implement `src/loopplane/model/capabilities.py`: a `runtime_checkable` `MediaCapableModel` Protocol (`accepts_media() -> bool`) + `accepts_media(model) -> bool` (probe, conservative `False`). Export `accepts_media` from `src/loopplane/model/__init__.py` (`__all__`). The `ModelBoundary` Protocol is UNCHANGED.
- [ ] T005 Add the adapter opt-in (additive defaults): `AnthropicConfig.accepts_media: bool = True` + `AnthropicModel.accepts_media()`; `OpenAIConfig.accepts_media: bool = True` + `OpenAIModel.accepts_media()`; `openrouter_model(accepts_media=True)` / `ollama_model(accepts_media=False)` threading the flag into the `OpenAIConfig`.

## Phase 3: User Story 1 — image input end-to-end (P1)

- [ ] T006 [US1] Tests (write first) in `tests/unit/test_multimodal_assembly.py`: `assemble_blocks` embeds an image upload as a leading `ImageBlock` (correct `media`/`format`) ahead of the `TextBlock(prompt)`; a non-image upload yields no block; multiple uploads keep image order; a missing/non-owned ref raises `UnknownUpload`; an oversized image raises `MediaTooLarge`; empty uploads → `[TextBlock]`. Plus `image_media_type` detection (png/jpeg/gif/webp by magic bytes + extension; non-image → `None`).
- [ ] T007 [US1] Implement the pure image-type detector `image_media_type(name, data)` in `src/loopplane/webapi/uploads.py` (stdlib only) and `src/loopplane/webapi/multimodal.py` `assemble_blocks(prompt, refs, store, owner, *, accepts_media, max_image_bytes)` + the `UnknownUpload` / `MediaNotAccepted` / `MediaTooLarge` errors.
- [ ] T008 [US1] Wire the web edge: add `UploadRef` + `RunRequest.uploads` and `ModelInfo.accepts_media` in `src/loopplane/webapi/models.py`; export `RunRequest`/the assembly name from `src/loopplane/webapi/__init__.py`. In `src/loopplane/webapi/app.py` add `ModelHost.accepts_media` + `create_app(default_accepts_media=...)`, a `_select` returning `(host, accepts_media)`, and have `/runs`, `/runs/events`, `/sessions/{id}/submit` build blocks via `assemble_blocks` and drive with the assembled `ContentBlock`s; update `run_event_stream` in `streaming.py` to accept assembled blocks.
- [ ] T009 [US1] Integration tests in `tests/integration/test_webapi_multimodal.py`: a run carrying an uploaded image makes the scripted model receive a leading `ImageBlock` (assert via a recording model or the history/blocks); a non-image upload is not embedded; a missing/non-owned ref → 400; an oversized image → 413; no uploads → identical text-only behavior.

## Phase 4: User Story 2 — graceful degradation (P1)

- [ ] T010 [US2] Integration tests in `tests/integration/test_webapi_multimodal.py`: a run carrying an image against a host whose `accepts_media` is `False` → HTTP 400 `ErrorResponse`, no image dispatched; `/v1/models` reports `accepts_media` per entry; a media-capable host dispatches the image (US1).

## Phase 5: Constitution VI — schema round-trip proof

- [ ] T011 Extend `tests/contract/test_runtime_events.py`: assert an `ImageBlock`-bearing `UserInputEvent` serializes + deserializes losslessly (the content-block input path is contract-safe; `SCHEMA_VERSION` unchanged).

## Phase 6: Polish & Cross-Cutting

- [ ] T012 Add `accepts_media` under `### loopplane.model` in `docs/api-reference.md` (and any new `loopplane.webapi` public name) so the unit-014 bijection (`tests/contract/test_api_reference.py`) stays green.
- [ ] T013 Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green (prior suite + new tests).
- [ ] T014 Tracking: `CHANGELOG.md` (a `**036**` entry after `**035**`), `docs/loopplane-agent-board.md` (§3 row + §4 → Tier-1 sprint 033–036 complete; note deferred PDF + native Gemini), `.specify/feature.json` → `specs/036-multimodal-input`, `CLAUDE.md` SPECKIT pointer → the 036 plan.

## Dependencies & Execution Order

- T001/T002 → T003/T004 → T005 → (US1 T006/T007/T008/T009) → (US2 T010) → T011 → T012 → T013 → T014.
- US1 and US2 share the model probe (T004) and the web edge (T008), so they land together.

## Notes

- No new dependency; no content-model or event-schema change (ADR D1); no
  `SCHEMA_VERSION` bump; the `ModelBoundary` Protocol stays two methods.
- PDF / `DocumentBlock`, binary artifact durability, and the gateway non-text
  oversized-output handoff are the ADR's recommended **follow-up** (D2/D3/D4) — out
  of scope here. Native Gemini is a separate deferred 035 follow-up.
- Rollback = remove the `RunRequest.uploads` field + `webapi/multimodal.py` + the
  `image_media_type` helper + the `accepts_media` flags + the api-reference
  additions (Constitution X).
