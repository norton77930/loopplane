# Implementation Plan: Real Model-Provider Adapters

**Branch**: `020-model-provider-adapters` (main-only) | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-model-provider-adapters/spec.md`

## Summary

Ship two real model-provider adapters — **Anthropic** (`loopplane.adapters.anthropic`)
and **OpenAI** (`loopplane.adapters.openai`) — that implement the existing model
boundary (`stream_turn` + `context_capacity`) unchanged, so an embedder can set
`RuntimeConfig(model=AnthropicModel(...))` or `OpenAIModel(...)`, inject their own API
key, and drive the agent loop against a real model. Each adapter wraps its **official
SDK** behind its own **optional extra** (`anthropic`, `openai`), mirroring how
`loopplane.adapters.mcp` confines the `mcp` SDK. The hard part — translating the loop's
`ContentBlock` history and `ToolDescriptor`s into each provider's request, and the
provider's streamed events back into the normalized increment union — is done by
**duck-typing the provider event objects** (the same `getattr`/`isinstance` style the
MCP adapter already uses), so the stream mapping is decoupled from fragile SDK type
names and is testable with plain stand-in events. SDK client construction is isolated
behind an injectable factory, so the offline tests need no SDK network and no
credentials. The runtime core is untouched; the unit is purely additive.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: the `anthropic` and `openai` official SDKs, each an **optional
extra** (and in the dev group for `mypy`/tests). No new runtime-core dependency — the
core install stays `anyio + pydantic + jsonschema`.

**Storage**: N/A (adapters are stateless; the host's configured stores apply as before)

**Testing**: `pytest`. Offline, deterministic tests drive each adapter with a **stub
client** that yields stand-in provider events (text, tool-use, overflow, error). A
single **opt-in, secret-gated** live test (`skipif` on the absence of an API-key env
var) carries the foundation unit's reserved real-model validation; it is excluded from
the default CI gates.

**Target Platform**: a Python library (embeddable runtime)

**Project Type**: library — two model-boundary adapter subpackages under
`src/loopplane/adapters/`

**Performance Goals**: streaming, incremental; wall-clock bound by the provider

**Constraints**: no runtime-core change; each adapter module imports its SDK **lazily**
(importable without the SDK, like the MCP adapter); credentials are injected, never
committed; provider differences never surface in the loop contract or event stream

**Scale/Scope**: two adapter subpackages + their mapping modules + tests + two examples
+ one doc; edits to `pyproject.toml`, the API reference, the docs/examples indexes, the
changelog, and the packaging contract test's extras set

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md`. | PASS |
| II — Greenfield | Both adapters are written fresh; no legacy code copied. | PASS |
| III — Harness before automation | Adapters sit at the model seam; they add no loop automation. | PASS |
| IV — Boundary Clarity | Each adapter is one declared `ModelBoundary` implementation; it reaches into no other component. | PASS |
| V — Tool Gateway Ownership | The adapter surfaces model tool calls as raw `ToolCallRequest`; the gateway alone validates/authorizes/executes them. | PASS (FR-003) |
| VI — Event Bus Ownership | The adapter only yields normalized increments; the loop emits the events. Provider specifics stay inside the adapter. | PASS (FR-002, FR-011) |
| VII — Public-Safe | Credentials are injected, never committed; non-overflow faults raise a fresh public-safe message; the loop already keeps raw model errors off the event stream. | PASS (FR-005, FR-006) |
| VIII — No SDK Replacement | The SDKs enter **only** as model-boundary adapters; the runtime core (loop, controller, gateway, event bus) is unchanged. | PASS (FR-001, FR-010) |
| IX — Reference, not clone | Mapping is re-derived from each provider's public streaming shape; nothing is cloned. | PASS |
| X — Testable Evolution | Offline stub tests are the default gate; live is opt-in/secret-gated; rollback = delete the two subpackages + their extras. | PASS (FR-009) |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-model-provider-adapters/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── model-provider-adapter.md   # the adapter contract: stream mapping, overflow, errors, injectable client
│   └── integration-boundary.md     # extras, lazy import, api-reference, no core change
├── checklists/requirements.md
└── tasks.md                        # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/adapters/
├── anthropic/                      # NEW — Anthropic (Claude) adapter
│   ├── __init__.py                 # __all__ = AnthropicModel, AnthropicConfig
│   ├── config.py                   # AnthropicConfig: model name, capacity, injectable client factory
│   ├── mapping.py                  # ContentBlock/ToolDescriptor -> request; stream event -> increment (duck-typed)
│   └── adapter.py                  # AnthropicModel: ModelBoundary (stream_turn, context_capacity)
└── openai/                         # NEW — OpenAI (GPT) adapter (same four-file shape)
    ├── __init__.py
    ├── config.py
    ├── mapping.py
    └── adapter.py

tests/
├── unit/
│   ├── test_anthropic_mapping.py   # pure mapping: blocks->request, events->increments
│   └── test_openai_mapping.py
├── integration/
│   ├── test_us1_model_providers.py # parametrized over both adapters: text + tool-use loop via stub client
│   ├── test_us2_model_overflow.py  # both adapters raise ContextOverflowError -> loop compacts & retries once
│   └── test_us3_model_failures.py  # both adapters: normalized/public-safe failure + usage mapping
└── live/
    └── test_live_models.py         # opt-in, secret-gated (skipif no key) — NOT in default CI

examples/anthropic_quickstart.py    # env-injected key; lazy import; safe no-key exit
examples/openai_quickstart.py
docs/model-providers.md             # the guide
```

Edited (additive, traceable):

```text
pyproject.toml                       # + [anthropic]/[openai] extras; + dev SDKs
docs/api-reference.md                # + the two adapter package sections
docs/README.md                       # + link model-providers.md
examples/README.md                   # + list the two examples
CHANGELOG.md                         # + a 020 Added entry
tests/contract/test_packaging.py     # extras set now {anthropic, mcp, openai, otel, web}
```

**Structure Decision**: Two adapter subpackages under the existing
`src/loopplane/adapters/` (the home of the MCP adapter), each a public package with
`__all__`, each importable without its SDK (the SDK is imported lazily inside the client
factory and not at module top). The mapping logic consumes provider events by
duck-typing, so the offline tests inject plain stand-in events and need no SDK. The opt-in
live test and the runnable examples carry the real-model validation outside CI.

## Phases

- **Phase 0 — Research** (`research.md`): the model-boundary seam and how it differs
  from the gateway error path; the duck-typed mapping decision; the injectable client
  factory; each provider's streaming shape (text / reasoning / tool-use / usage /
  overflow); the optional-extra + lazy-import pattern; and the offline-stub vs opt-in-live
  testing split, including the packaging/api-reference contract obligations.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the adapter
  classes and config; the `ContentBlock`↔provider-message and stream-event↔increment
  mapping tables; the adapter contract; the integration boundary; and a usage quickstart.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — per-provider mapping tests + impl, then
  the parametrized loop integration tests (US1–US3) + the adapters, then the packaging /
  api-reference / docs / changelog wiring, then the opt-in live test, examples, and guide.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
