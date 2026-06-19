# Implementation Plan: Native Google Gemini Model-Provider Adapter

**Branch**: `037-gemini-adapter` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/037-gemini-adapter/spec.md`

## Summary

Add a new public package `loopplane.adapters.gemini` — `GeminiConfig`,
`GeminiModel`, and a request/stream `mapping` — implementing the existing
`ModelBoundary` over the **direct** Google GenAI API (the official `google-genai`
SDK), behind a new optional extra **`gemini`**. The adapter mirrors the unit-020
Anthropic/OpenAI adapters exactly: the SDK is imported **lazily** inside the
client factory (so the package imports without the extra), the provider stream is
consumed by **duck-typing** (so the mapping needs no SDK types), and the whole
adapter is tested **offline with a stub client** (no SDK, no network). It adds the
additive duck-typed `accepts_media()` signal (unit 036; default `True`, Gemini is
vision-capable) and registers as a `/v1/models` host like every other adapter, so
the existing selector lists it with no frontend change.

**The shared content model and the event schema are UNCHANGED.** Gemini 3
hard-requires a per-`function_call` `thought_signature` for multi-turn tool use,
but Google provides an official `"skip_thought_signature_validator"` sentinel that
**skips validation** — so the adapter makes multi-turn tool use *work* by attaching
that sentinel when re-mapping a prior `ToolCallBlock`, **without** adding a field
to `ToolCallBlock` and **without** a `SCHEMA_VERSION` bump. Preserving the *real*
per-call signature (for best cross-turn reasoning continuity) would need a
content-model field — a Constitution VI / ADR matter — and is a documented,
deferred follow-up. No ADR is therefore required for this unit (it changes neither
the content model nor the event schema); it references the existing ADR 0001 (D1's
"content model unchanged" philosophy, D5's duck-typed `accepts_media`).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: a new optional extra **`gemini`** = the official
**`google-genai`** SDK (`google-genai>=1`), imported **lazily** inside the client
factory. No required runtime dependency added.

**Storage**: N/A

**Testing**: pytest (offline) — a Gemini-shaped stub client yielding stand-in
`SimpleNamespace` chunks (text + `function_call` framing + `usage_metadata` + an
overflow/error signal) drives a real decode; an injected client bypasses the SDK
entirely. Mirrors the unit-020 offline-stub posture. Any live check is opt-in /
secret-gated and excluded from the default gates.

**Target Platform**: cross-platform library runtime

**Project Type**: single project — embeddable Python library/runtime

**Constraints**: no change to the runtime core, the gateway, the event bus, **the
content model, or the event schema** (no `SCHEMA_VERSION` bump); the credential is
injected, never committed; the Tool Gateway owns tool validation (the adapter
surfaces raw `ToolCallRequest`s).

**Scale/Scope**: one new public package (4 modules; 2 public names —
`GeminiModel`, `GeminiConfig`) + one offline unit-test module (+ a shared
integration stub + an opt-in live check) + a `gemini` extra + an api-reference
section + a model-registry/example touch.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 037; the deferred 035 follow-up, named in 035 research Decision 2 and ADR 0001 Follow-up #3).
- **II — Greenfield**: PASS (a fresh adapter written for this repo; no legacy copied; the unit-020 adapter shape is the in-repo precedent it mirrors).
- **III — Agent Harness Before Loop Automation**: N/A (no loop-automation surface; a model-boundary adapter only).
- **IV — Runtime Boundary Clarity**: PASS (lives entirely at the existing model-boundary seam; no runtime-core/gateway/event-bus change; **no content-model change → no boundary-blurring → no ADR required**, unlike 036 which did touch the model-selecting edge).
- **V — Tool Gateway Ownership**: PASS (the adapter surfaces tool calls as **raw** `ToolCallRequest`s with args passed through; it validates/executes nothing — the gateway owns that).
- **VI — Event Bus**: PASS (only normalized increments reach the loop, via the new mapping; **the event schema and content model are UNCHANGED** — no new `ToolCallBlock` field, no `SCHEMA_VERSION` bump; the conservative `thought_signature` path uses Google's official sentinel instead of a content-model carrier).
- **VII — Public-Safe**: PASS (no key committed; the Google key is injected/env via the lazy client factory; provider errors normalized to a public-safe `ModelProviderError` with no key/raw-body leak).
- **VIII — No SDK Replacement**: PASS — **the headline gate**: the Google GenAI SDK enters **ONLY as a model-boundary adapter** (implementing the unchanged `ModelBoundary` = `stream_turn` + `context_capacity`); the runtime core (Agent Loop, Controller, Dispatcher, Tool Gateway, Event Bus) is unchanged.
- **IX — Reference, not clone**: PASS (the Gemini wire mapping is re-derived for Gemini's own `contents`/`parts`/`function_declarations`/`usage_metadata` shape; the adapter *structure* mirrors the in-repo unit-020 precedent rather than copying any external framework).
- **X — Testable Evolution**: PASS (deterministic offline stub tests written first; rollback = delete the package + test module + the `gemini` extra + the api-reference section; units 020/035/036 untouched).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/037-gemini-adapter/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/model-provider-adapter.md, contracts/integration-boundary.md
└── checklists/requirements.md
```

No ADR is added (the content model and event schema are unchanged; the conservative
`thought_signature` path uses Google's official sentinel). The unit references the
existing `docs/adr/0001-multimodal-content.md` (D1 "content model unchanged"; D5
duck-typed `accepts_media`; Follow-up #3 names this native-Gemini unit).

### Source Code (repository root)

```text
src/loopplane/adapters/
├── anthropic/           # USE (unchanged): the unit-020 adapter shape this mirrors
├── openai/              # USE (unchanged)
├── openai_compat/       # USE (unchanged): the 035 OpenRouter path Gemini was reachable through
├── _model_errors.py     # USE (unchanged): ModelProviderError + error_text (shared)
└── gemini/              # NEW package (mirrors the 020 four-file shape)
    ├── __init__.py      # GeminiModel, GeminiConfig (+ __all__)
    ├── config.py        # GeminiConfig + default_client_factory (lazy `google.genai` import)
    ├── mapping.py       # build_contents, build_tools, GeminiStreamDecoder (duck-typed)
    └── adapter.py       # GeminiModel: stream_turn / context_capacity / accepts_media

src/loopplane/model/content.py   # UNCHANGED (no ToolCallBlock signature field)
src/loopplane/events/            # UNCHANGED (no SCHEMA_VERSION bump)

pyproject.toml           # MODIFY: add the `gemini` extra (google-genai) + dev group
docs/api-reference.md    # MODIFY: + `### loopplane.adapters.gemini` section (014 bijection)
docs/real-model-validation.md    # MODIFY: note the per-provider live Gemini check env vars

tests/unit/
└── test_gemini_mapping.py        # NEW: offline request-mapping + stream-decoding tests
tests/integration/
├── provider_stubs.py             # MODIFY: add a Gemini-shaped stub client + chunk builder
├── test_us2_model_overflow.py    # USE (parametrized): gains "gemini" via PROVIDERS
└── test_us3_model_failures.py    # USE (parametrized): gains "gemini" via PROVIDERS
tests/unit/test_capabilities.py   # MODIFY: assert the Gemini adapter accepts_media default
tests/live/test_live_models.py    # MODIFY: add an opt-in, secret-gated Gemini live turn
```

**Structure Decision**: A dedicated four-file `gemini` package (mirroring the
unit-020 `anthropic`/`openai` packages — `config.py` / `mapping.py` / `adapter.py`
/ `__init__.py`) is the right shape because Gemini is a **native** adapter with its
own wire format, unlike the 035 OpenAI-compatible providers (which were thin
`base_url` wrappers in a single module reusing `OpenAIModel`). It reuses the shared
`adapters/_model_errors.py` (`ModelProviderError` + `error_text`) so error
normalization is consistent across adapters. The duck-typed stream mapping +
injected-client testability keep the unit offline-testable and the SDK an optional
extra, exactly as unit 020.

## Complexity Tracking

> No Constitution Check violations. The content model and event schema are
> unchanged (no ADR required); the `thought_signature` decision is recorded in
> `research.md` (Decision 3).

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
