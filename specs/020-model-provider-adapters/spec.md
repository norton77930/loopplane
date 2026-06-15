# Feature Specification: Real Model-Provider Adapters

**Feature Branch**: `020-model-provider-adapters` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Real model-provider adapters implementing the existing model boundary (unit 020): ship two adapters — Anthropic (Claude) and OpenAI (GPT) — each using its official SDK behind its own optional extra, so an embedder can bring an API key and drive the agent loop with a real model. The runtime core is unchanged; the adapters only implement the existing model-boundary seam."

## Overview

The runtime has exactly one model-facing seam — the **model boundary** (`stream_turn` +
`context_capacity`) — and a deterministic **scripted model** ships as its test
instrument. No real model-provider integration exists; the boundary's own note states
that provider integrations were not a foundation deliverable. As a result the whole
control plane (observable, governed, tool-using runs) has only ever been exercised
against a scripted stub.

This unit closes that gap by shipping **two real model-provider adapters — Anthropic
(Claude) and OpenAI (GPT)** — that implement the existing model boundary unchanged.
Each adapter wraps its **official SDK**, isolated behind its own **optional extra**
(mirroring how the MCP tool adapter confines the `mcp` SDK), and translates the
provider's streaming output into the loop's normalized increments. An embedder
configures one as the runtime's model, brings their own API key by injection, and runs
the agent loop — text turns, tool-use round-trips, context-overflow compaction, and
normalized failures — with no change to the loop's consumption contract. Live model
verification (the manual real-model validation reserved in the foundation unit) is
carried by this unit's opt-in, secret-gated tests; the default gates stay offline and
deterministic.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drive a real run with a real model (Priority: P1)

An embedder sets the runtime's model to a real provider adapter (Anthropic or OpenAI),
injects their own API key, and runs the agent loop through both a **plain text turn**
and a **tool-use turn** — the model requests a tool, the gateway executes it, the
result is fed back, and the model continues to an end-of-turn.

**Why this priority**: A real model driving a real loop — including the tool-use
round-trip — is the entire point of the unit and exercises the full mapping path
(provider stream → normalized increments → gateway → continuation).

**Independent Test**: Drive each adapter with a stubbed transport that emulates the
provider's stream and assert, **parameterized over both adapters**, that the stream is
mapped to ordered increments (text and tool-call) and that a tool-use round-trip
completes through the gateway.

**Acceptance Scenarios**:

1. **Given** an adapter configured with one internal tool, **When** the model emits a tool call, **Then** the loop executes the tool through the gateway, feeds the result back, and the model continues to an end-of-turn.
2. **Given** a plain text turn, **When** the adapter streams text, **Then** it produces ordered `TextIncrement`s followed by a `TurnEnd`.

### User Story 2 - Context-overflow compaction is consistent (Priority: P2)

When the assembled context exceeds the model's capacity, the adapter signals the
loop's distinct overflow condition so the loop compacts and retries exactly once —
the same behavior for both providers.

**Why this priority**: Overflow handling is an existing, relied-upon loop behavior;
each adapter must trigger it correctly or long runs break.

**Independent Test**: Have each adapter's stub report a capacity-exceeded signal and
assert the adapter raises the overflow condition and the loop performs its single
compact-and-retry.

**Acceptance Scenarios**:

1. **Given** an assembled context over capacity, **When** the adapter runs the turn, **Then** it raises the context-overflow condition and the loop compacts and retries once.

### User Story 3 - Failures are normalized; usage is reported (Priority: P3)

Provider and transport errors surface as the loop's normalized errors — never leaking
the API key or raw SDK internals — and token usage is reported back when the provider
supplies it.

**Why this priority**: Public-safety and observability across the boundary; a leaked
key or raw stack trace is unacceptable, and usage feeds cost/observability.

**Independent Test**: Inject timeouts, mid-stream errors, and 4xx responses into each
adapter's stub and assert the outward result is a normalized error with no secret or
internal leakage, and that `TurnEnd.usage` carries the mapped token counts.

**Acceptance Scenarios**:

1. **Given** a provider/transport error, **When** the turn runs, **Then** the caller and the event stream see a normalized error with no key, no raw SDK exception, and no internal detail.
2. **Given** a successful turn, **When** the provider reports usage, **Then** `TurnEnd.usage` carries the mapped input/output/cached/reasoning counts.

### Edge Cases

- **Missing or invalid API key** → a normalized configuration/auth error, never an echoed credential.
- **Network timeout / mid-stream disconnect** → a normalized transport error; no partial increment leaks raw internals.
- **Malformed tool input from the model** → surfaced as a raw `ToolCallRequest`; the gateway (not the adapter) validates it.
- **Rate limit (429)** → a normalized error category; no retry storm beyond the loop's defined behavior.
- **Empty tool list** → a plain text turn runs with no tools advertised.
- **Provider-specific reasoning representation differs** → each adapter maps reasoning to `ReasoningIncrement` or omits it, without diverging the loop contract.
- **Tool-call stream framing differs by provider** (block-oriented vs incremental tool-call deltas) → each adapter reassembles a complete `ToolCallRequest` correctly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unit MUST provide two adapters — Anthropic and OpenAI — that implement the existing model boundary (`stream_turn`, `context_capacity`) with **no change to the loop's consumption contract**.
- **FR-002**: Each adapter MUST translate the provider's streaming output into the normalized increment union (`TextIncrement`, `ReasoningIncrement`, `ToolCallRequest`, `TurnEnd`) in order.
- **FR-003**: Each adapter MUST translate the registered tool descriptors into that provider's tool format and surface the model's tool calls as `ToolCallRequest` with **raw input**, leaving validation to the gateway (Constitution V).
- **FR-004**: When the provider reports the context exceeds capacity, the adapter MUST raise the loop's distinct context-overflow condition so the loop compacts and retries exactly once.
- **FR-005**: Provider and transport errors MUST be normalized and MUST NOT leak the credential, the raw SDK exception, or any internal detail to callers or the event stream (Constitution VII).
- **FR-006**: Credentials MUST be supplied by injected configuration/environment and MUST NOT be read from or written to committed files (Constitution VII).
- **FR-007**: When the provider supplies it, each adapter MUST report token usage via `TurnEnd.usage`, mapping the provider's fields to the normalized usage shape.
- **FR-008**: Each provider SDK MUST be its own optional extra (`anthropic`, `openai`); the core install MUST NOT require either, and each adapter MUST import its SDK only under its extra (mirroring the MCP adapter's isolation).
- **FR-009**: Both adapters MUST be covered by offline, deterministic tests using a stubbed transport (one set per provider); any live-model test MUST be opt-in and secret-gated, excluded from the default CI gates.
- **FR-010**: This unit MUST NOT change the runtime core or replace it with an external agent framework; the SDKs enter only as model-boundary adapters (Constitution VIII).
- **FR-011**: Both adapters MUST produce consistent observable loop behavior (text, tool-use, overflow, error normalization); provider-specific differences MUST stay inside the adapter's internal mapping and MUST NOT surface in the loop contract or event stream.

### Key Entities

- **Provider adapter**: a model-boundary implementation wrapping one provider's official SDK, translating its streaming turn and tool format to/from the normalized shapes.
- **Increment mapping**: the per-provider translation from provider stream events to the normalized increment union, including tool-call reassembly and usage mapping.
- **Stub transport**: the offline test double that replays a provider's stream shape (including overflow and error signals) so the adapters are tested deterministically without network or credentials.
- **Adapter configuration**: the injected settings (model name, credential source, limits) an embedder supplies to construct an adapter; credentials are never committed.

### Out of Scope

- Any change to the runtime core, the gateway, the event bus, or the loop's consumption contract; this unit only adds adapters at the existing seam.
- Additional providers beyond Anthropic and OpenAI (e.g., local/self-hosted models) — reserved for a later unit at the same seam.
- Retry/backoff policy, prompt caching strategy, or cost budgeting beyond reporting usage — these belong to existing/other layers, not the adapter.
- Running live-model tests in the default CI gates; live verification is opt-in and secret-gated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two documented examples each run a real text turn — one against Claude, one against GPT — using only an injected API key, with no code change.
- **SC-002**: A tool-use round-trip (model requests a tool → gateway executes → result returns → model continues) completes for each adapter.
- **SC-003**: Every provider/transport error path produces a normalized error with zero credential or internal leakage, verified by tests and the public-safety scan.
- **SC-004**: The core install (without either provider SDK) succeeds, and each adapter imports its SDK only under its corresponding extra.
- **SC-005**: The existing four quality gates stay green, and both providers' offline adapter test sets pass deterministically.

## Assumptions

- **Both providers, official SDKs**: Anthropic and OpenAI ship together in this unit, each wrapping its official SDK behind its own optional extra; other providers reuse the same seam in a later unit.
- **Existing seam, unchanged loop**: the adapters implement the existing model boundary; the loop's context-overflow compaction and tool-use handling are reused as-is, not redesigned here.
- **Injected credentials only**: API keys are provided by the embedder via configuration/environment and never appear in committed files.
- **Testable core, opt-in live**: offline stub-transport tests are the default, deterministic gate; live-model runs are opt-in and secret-gated and carry the foundation unit's reserved real-model validation.
- **Additive, reversible**: the unit is purely additive (new adapter modules and optional extras); removing it leaves the core and the scripted model untouched (Constitution X rollback).
