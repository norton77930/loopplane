# Implementation Plan: OpenAI-Compatible Model Providers (OpenRouter + Ollama)

**Branch**: `035-openai-compatible-providers` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/035-openai-compatible-providers/spec.md`

## Summary

Add a new public package `loopplane.adapters.openai_compat` with two thin
constructors — `openrouter_model(...)` and `ollama_model(...)` — that build a
unit-020 `OpenAIModel` whose client points at an OpenAI-compatible endpoint via a
`base_url` override. They **reuse** `OpenAIModel` + `openai/mapping.py` unchanged
(the OpenAI wire format), riding the existing `openai` extra (no new dependency).
The SDK is imported lazily inside a client-factory closure, so the package
imports without the extra and is tested offline. The existing `/v1/models`
registry and UI selector surface the providers with no frontend change. Native
Gemini is out of scope (deferred follow-up; reachable via OpenRouter).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new — reuses the existing optional `openai` extra
(`openai>=1.50`), imported lazily.

**Storage**: N/A

**Testing**: pytest (offline) — a fake `openai` module recording client kwargs +
an injected-client reuse assertion. Mirrors the 020 offline-stub posture.

**Target Platform**: cross-platform library runtime

**Project Type**: single project — embeddable Python library/runtime

**Constraints**: no change to the unit-020 OpenAI adapter/mapping, the runtime
core, the gateway, or the event bus; credentials injected, never committed.

**Scale/Scope**: one new public package (4 public names) + one offline test
module + an api-reference section + a model-registry/example touch.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 035).
- **II — Greenfield**: PASS (new constructors; no legacy copied).
- **IV — Runtime Boundary Clarity**: PASS (lives at the existing model-boundary seam; no core change).
- **V — Tool Gateway Ownership**: N/A (no tool concern).
- **VI — Event Bus**: PASS (no event change; only normalized increments reach the loop, via the reused OpenAI mapping).
- **VII — Public-Safe**: PASS (no key committed; OpenRouter key injected; Ollama placeholder; lazy SDK import).
- **VIII — No SDK Replacement**: PASS (the SDK enters only as a model-boundary adapter, reusing 020; the runtime core is unchanged).
- **IX — Reference, not clone**: PASS (reuses the OpenAI adapter rather than re-deriving an OpenAI-compatible client; OpenRouter/Ollama differences are confined to `base_url`).
- **X — Testable Evolution**: PASS (offline tests; rollback = delete the package + its api-reference section).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/035-openai-compatible-providers/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/adapters.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/adapters/
├── openai/              # USE (unchanged): OpenAIModel, OpenAIConfig (client_factory seam)
└── openai_compat/       # NEW package
    └── __init__.py      # openrouter_model, ollama_model, OPENROUTER_BASE_URL, OLLAMA_BASE_URL (+ __all__)

docs/api-reference.md    # MODIFY: + `### loopplane.adapters.openai_compat` section (014 bijection)

tests/unit/
└── test_openai_compat.py   # NEW: offline base_url-wiring + reuse tests
```

**Structure Decision**: A dedicated `openai_compat` package (not folding into the
`openai` package) keeps the provider concern cohesive and gives a clean public
surface. It reuses `OpenAIModel`/`OpenAIConfig` via the existing
`client_factory` seam, so unit 020 is untouched.

## Complexity Tracking

> No Constitution Check violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
