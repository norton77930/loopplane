# Feature Specification: OpenAI-Compatible Model Providers (OpenRouter + Ollama)

**Feature Branch**: `035-openai-compatible-providers` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "More providers (the multi-provider Tier-1 unit). Ship the OpenAI-compatible providers — OpenRouter and Ollama — as thin config wrappers that reuse the existing OpenAI adapter via a base_url override, lighting up the existing model selector with no frontend change. Native Gemini (direct Google API) is deferred to a follow-up; Gemini is reachable today via OpenRouter."

## Overview

The runtime ships two real model adapters (unit 020) — Anthropic and OpenAI —
each implementing the model boundary behind its own optional extra. The web UI
already has a model selector backed by the `/v1/models` registry (unit 028). But
the backend can only be configured with two providers, so the selector lists
only Anthropic/OpenAI hosts.

This unit widens provider reach **without a new adapter or dependency** by adding
two **OpenAI-compatible** providers — **OpenRouter** and **Ollama** — as thin
constructors that **reuse the unit-020 `OpenAIModel` and its chat-completions
mapping unchanged**, differing only in the client's `base_url` (and OpenRouter's
injected key). OpenRouter brokers 100+ models (Claude, Gemini, Llama, …) behind
the OpenAI wire format, so this single unit unlocks a large model catalog; Ollama
points the same adapter at a local daemon for credential-free local models. Both
plug into the existing host/registry the same way the OpenAI host does, so the
existing selector lists them with **no frontend change**.

A **native** Gemini adapter (direct Google GenAI API, to preserve
`thought_signature` across multi-turn tool use) is intentionally **out of scope
here** and deferred to a follow-up — Gemini is reachable today via OpenRouter.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drive a run through OpenRouter (Priority: P1)

An embedder configures an OpenRouter-backed model host (a model id + an injected
OpenRouter key), and the agent loop runs against it exactly as it does against
the OpenAI adapter — because it *is* the OpenAI adapter, pointed at OpenRouter's
OpenAI-compatible endpoint.

**Why this priority**: OpenRouter is the high-leverage win — one wrapper unlocks
100+ models behind the proven OpenAI mapping.

**Independent Test**: Build an OpenRouter model with a stubbed client and assert
it is an `OpenAIModel` (mapping reused), and that the client is constructed with
the OpenRouter `base_url` and the injected key.

**Acceptance Scenarios**:

1. **Given** an OpenRouter model id and key, **When** the model is built, **Then** the underlying OpenAI client is constructed with OpenRouter's `base_url` and the injected key.
2. **Given** an OpenRouter model, **When** the loop streams a turn, **Then** the existing OpenAI stream mapping (text, tool calls, usage, overflow) applies unchanged.

### User Story 2 - Drive a run through a local Ollama (Priority: P2)

An embedder points the same wrapper at a local Ollama OpenAI-compatible endpoint
(no API key needed) and runs the loop against a local model.

**Why this priority**: Local, credential-free models are a common dev/offline
need and come almost for free once the base_url seam exists.

**Independent Test**: Build an Ollama model with a stubbed client and assert the
client uses the local Ollama `base_url` and a placeholder key, and that a custom
`base_url` is honored.

**Acceptance Scenarios**:

1. **Given** no API key, **When** an Ollama model is built, **Then** the client uses the local Ollama `base_url` and a placeholder key (Ollama ignores it).
2. **Given** a custom Ollama `base_url`, **When** the model is built, **Then** that base_url is used.

### Edge Cases

- **Missing `openai` extra** → the same lazy-import behavior as the OpenAI adapter (the SDK is imported only inside the client factory; the package imports without the extra).
- **Injected client (tests)** → bypasses the factory entirely, so offline tests need no SDK and no network.
- **Any provider/transport/overflow error** → handled by the reused `OpenAIModel` exactly as for OpenAI (normalized error / `ContextOverflowError`); this unit adds no new error path.
- **Registry listing** → the new providers register as model hosts the same way the OpenAI host does, so `/v1/models` lists them with no UI change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unit MUST add two OpenAI-compatible providers — OpenRouter and Ollama — that **reuse** the unit-020 `OpenAIModel` and its chat-completions mapping **unchanged** (Constitution IX: reference/reuse, not re-implement).
- **FR-002**: OpenRouter MUST build the OpenAI client with OpenRouter's `base_url` and an injected API key (supplied by config/environment, never committed — Constitution VII).
- **FR-003**: Ollama MUST build the OpenAI client with a local (overridable) `base_url` and MUST NOT require a real API key (a placeholder satisfies the SDK).
- **FR-004**: Both providers MUST implement the existing model boundary with **no change** to the loop's consumption contract, the runtime core, the gateway, or the event bus (Constitution IV/VIII).
- **FR-005**: The SDK MUST be imported lazily (only inside the client factory), so the package imports without the `openai` extra and is tested offline; both providers MUST accept an injected client for offline tests.
- **FR-006**: The unit MUST add **no new runtime dependency** (it rides the existing `openai` extra).
- **FR-007**: Both providers MUST register as model hosts the same way the OpenAI host does, so the existing `/v1/models` registry and UI selector surface them with **no frontend change**.
- **FR-008**: The new public package (`loopplane.adapters.openai_compat`) MUST declare `__all__` and be documented in `docs/api-reference.md` so the unit-014 reference bijection stays green.
- **FR-009**: The unit MUST be covered by deterministic offline tests (a fake `openai` module that records the client kwargs + an injected-client reuse assertion); any live check is opt-in.

### Key Entities

- **`openrouter_model(...)`**: a constructor returning an `OpenAIModel` whose client targets OpenRouter's OpenAI-compatible endpoint.
- **`ollama_model(...)`**: a constructor returning an `OpenAIModel` whose client targets a local Ollama OpenAI-compatible endpoint with a placeholder key.
- **base_url client factory**: a small factory closure that mirrors the OpenAI adapter's default client factory but pins the `base_url`.

### Out of Scope

- **Native Gemini adapter** (direct Google GenAI API + `thought_signature` multi-turn preservation) — deferred to a follow-up; Gemini is reachable via OpenRouter today.
- Any change to the unit-020 OpenAI adapter, mapping, the runtime core, the gateway, or the event bus.
- Provider-specific features beyond the OpenAI wire format (e.g. OpenRouter routing preferences, Ollama model management).
- Server-side key management; keys are injected by the host.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An OpenRouter-backed model can be built with a model id + key, and it is an `OpenAIModel` whose client carries the OpenRouter `base_url` (verified offline).
- **SC-002**: An Ollama-backed model can be built with no key, targeting the local (or a custom) `base_url`, and is an `OpenAIModel`.
- **SC-003**: The core install (no `openai` extra) still imports the package; offline tests pass with no SDK and no network.
- **SC-004**: The four quality gates stay green, including the unit-014 api-reference bijection (the new package's `__all__` is documented).
- **SC-005**: Adding OpenRouter/Ollama to a `/v1/models` registry surfaces them in the existing UI selector with no frontend change.

## Assumptions

- **Reuse over re-implement**: OpenRouter and Ollama speak the OpenAI wire format, so the unit-020 `OpenAIModel` + mapping are reused unchanged via a `base_url` override (the `OpenAIConfig.client_factory` seam).
- **Injected credentials**: an OpenRouter key is host-injected; Ollama needs none (placeholder).
- **Native Gemini deferred**: shipping it well needs the Google GenAI SDK behind a new extra and careful `thought_signature` handling (a possible content-model concern); it is a follow-up. OpenRouter covers Gemini access in the meantime.
- **Additive, reversible**: removing the `openai_compat` package and its api-reference section leaves units 020/028 untouched (Constitution X rollback).
