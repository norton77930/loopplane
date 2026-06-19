# Feature Specification: Anthropic Prompt Caching (explicit cache breakpoints)

**Feature Branch**: `040-prompt-caching` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Tier-3 efficiency unit, cost-focused. Add explicit
Anthropic prompt-cache breakpoints so repeated turns re-read a cached stable
prefix at ~0.1x instead of full price. Transparent to the loop; additive;
reuse-first; offline-tested. OpenAI caching is already automatic — confirm and
document. No change to the loop, the event schema, the content model, the
gateway, or `TokenUsage`'s shape."

## Overview

The Anthropic adapter (unit 020) assembles each turn's request from the loop's
normalized shapes: a `messages` list (built by `build_messages`) and an optional
`tools` list (built by `build_tools`). Across an agent loop, the **front** of
that request is highly repetitive — the same tool definitions and the same
leading instructions/first user turn are re-sent on every turn — yet today every
turn pays full input-token price for that repeated prefix.

Anthropic supports **prompt caching**: attaching `cache_control: {"type":
"ephemeral"}` to the last content block of a stable prefix makes a subsequent
request that shares that exact prefix read it from cache at ~0.1x input price
(after a ~1.25x write on the first turn). The cache is a **prefix match** keyed
on the exact rendered bytes up to each breakpoint, the render order is `tools →
system → messages`, and the API allows at most **4** breakpoints per request.

This unit adds explicit cache breakpoints to the Anthropic request **on the
stable prefix only** (the tools block and a stable leading-history prefix —
never the rolling tail), behind a per-adapter config toggle. It is **transparent
to the loop**: caching changes only the provider request shape, not the loop's
behavior or the normalized event stream. Caching is already observable through
the existing `TokenUsage.cached_tokens` (mapped from Anthropic's
`cache_read_input_tokens` and OpenAI's `prompt_tokens_details.cached_tokens`),
so **no event/content/usage-shape change is needed**.

OpenAI (and the OpenAI-compatible OpenRouter/Ollama path, unit 035) caches
**automatically** — `cached_tokens` is already reported and **no request change**
is required there. This unit confirms and documents that.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repeated turns re-read a cached Anthropic prefix (Priority: P1)

An embedder runs a multi-turn agent loop against the Anthropic adapter with
caching enabled (the default). On the first turn the stable prefix (tool
definitions + the leading first user turn) is written to cache; on every
subsequent turn that same prefix is read from cache at ~0.1x instead of being
re-billed at full price.

**Why this priority**: This is the unit's entire cost-savings value — repeated
turns are the common agent-loop shape, and the prefix is the bulk of the
re-sent tokens.

**Independent Test**: Build the Anthropic request with caching ON and assert
`cache_control: {"type": "ephemeral"}` is attached to the last tool definition
and to the last content block of the leading stable message, that there are at
most 4 breakpoints, and that no breakpoint sits on the rolling last message.

**Acceptance Scenarios**:

1. **Given** caching is enabled and a request with tools + a multi-message
   context, **When** the Anthropic request is assembled, **Then**
   `cache_control: {"type": "ephemeral"}` is attached to the **last tool
   definition** (the end of the tools segment).
2. **Given** caching is enabled and a context with two or more messages, **When**
   the request is assembled, **Then** `cache_control` is attached to the **last
   content block of the leading stable message** (the first message) and **not**
   to the rolling last message.
3. **Given** any caching-enabled request, **When** it is assembled, **Then** the
   total number of `cache_control` breakpoints is **at most 4**.

### User Story 2 - Caching can be turned off with a byte-identical request (Priority: P1)

An embedder disables prompt caching (or runs against a model/account where it is
unwanted). The assembled Anthropic request is then **byte-identical** to the
pre-caching request — no `cache_control` anywhere, same `system`/`tools`/
`messages` shapes as today.

**Why this priority**: Additivity and reversibility (Constitution X) require the
off path to be provably unchanged, so caching is a pure, safe overlay.

**Independent Test**: Assemble the request with caching OFF and assert it equals
the output of the existing `build_messages` / `build_tools` exactly (no
`cache_control` key present).

**Acceptance Scenarios**:

1. **Given** caching is disabled, **When** the request is assembled, **Then** the
   `messages` and `tools` are exactly the existing `build_messages` /
   `build_tools` output (no `cache_control` anywhere).
2. **Given** caching is disabled, **When** a turn streams, **Then** the loop's
   normalized increments and `TokenUsage` are unchanged from today.

### User Story 3 - OpenAI caching is automatic and already reported (Priority: P2)

An embedder runs against the OpenAI adapter (or OpenRouter/Ollama, unit 035).
Caching happens automatically server-side with **no request change**, and the
`cached_tokens` it reports already flows into `TokenUsage.cached_tokens`.

**Why this priority**: It costs nothing to confirm and document, and it tells the
embedder the cross-provider caching story without a second implementation.

**Independent Test**: Feed the OpenAI stream decoder a usage chunk carrying
`prompt_tokens_details.cached_tokens` and assert `TokenUsage.cached_tokens` is
populated, while the request the adapter sends carries no cache parameter.

**Acceptance Scenarios**:

1. **Given** an OpenAI usage chunk with `prompt_tokens_details.cached_tokens =
   N`, **When** the stream finishes, **Then** `TurnEnd.usage.cached_tokens == N`.
2. **Given** the OpenAI adapter, **When** it assembles a request, **Then** it
   sends **no** cache-control parameter (caching is automatic).

### Edge Cases

- **No tools** → no tools breakpoint is added (the tools segment is absent); the
  messages-prefix breakpoint still applies.
- **Single-message context** → the only message *is* the stable leading prefix
  and also the (sole) last message; to never cache the rolling tail, the
  messages-prefix breakpoint is placed only when there is a message **before**
  the rolling last message (i.e. two or more messages). With a single message,
  only the tools breakpoint (if any) is added.
- **Empty content on the leading message** → no content block to mark; the
  messages-prefix breakpoint is skipped (defensive; the loop's first turn always
  has text).
- **Below the model's minimum cacheable prefix (~4096 tokens for Opus 4.x)** →
  the API silently does not cache (no error, `cache_read_input_tokens` stays 0).
  The breakpoint is harmless; correctness is unaffected.
- **Caching disabled** → the request is byte-identical to today (no
  `cache_control`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When prompt caching is enabled, the Anthropic adapter MUST attach
  `cache_control: {"type": "ephemeral"}` to the **last tool definition** of the
  `tools` block (when tools are present), marking the end of the stable tools
  segment.
- **FR-002**: When prompt caching is enabled and the context has two or more
  messages, the adapter MUST attach `cache_control: {"type": "ephemeral"}` to
  the **last content block of the first message** (a stable leading-history
  prefix) and MUST NOT attach any breakpoint to the rolling last message.
- **FR-003**: The adapter MUST never emit more than **4** `cache_control`
  breakpoints in a request (the Anthropic maximum), and MUST place breakpoints
  only on **stable** boundaries (tools + a stable leading message), never on the
  rolling tail.
- **FR-004**: Prompt caching MUST be controlled by an additive per-adapter
  config toggle (`AnthropicConfig.prompt_caching: bool`). When the toggle is
  **off**, the assembled request MUST be **byte-identical** to the pre-caching
  request (no `cache_control` anywhere; same `messages`/`tools` shapes).
- **FR-005**: The change MUST be **additive** and confined to the Anthropic
  adapter package (`anthropic/mapping.py` + `anthropic/config.py` + the adapter's
  request assembly). It MUST NOT change the loop, the runtime core, the Tool
  Gateway, the Runtime Event Bus, the event schema, the content model, or
  `TokenUsage`'s shape.
- **FR-006**: The existing `build_messages` / `build_tools` outputs MUST remain
  byte-identical (the breakpoints are applied by a separate, opt-in step), so the
  unit-020 mapping tests stay green unchanged and the off path is the existing
  behavior.
- **FR-007**: The OpenAI adapter (and the OpenAI-compatible OpenRouter/Ollama
  path, unit 035) MUST require **no request change**: caching is automatic, and
  `prompt_tokens_details.cached_tokens` is already mapped to
  `TokenUsage.cached_tokens` by the existing stream decoder. This unit confirms
  and documents that; it adds no OpenAI request parameter.
- **FR-008**: Caching MUST be observable through the **existing** usage
  (`TokenUsage.cached_tokens`, mapped from Anthropic `cache_read_input_tokens`
  and OpenAI `cached_tokens`). No new event, content block, or usage field is
  added.
- **FR-009**: The unit MUST be covered by **deterministic offline tests** (no
  live calls): caching-ON breakpoint placement (system/tools/stable-prefix, the
  4-max, never the rolling tail), caching-OFF byte-identity, and the OpenAI
  `cached_tokens` mapping from a stub usage chunk. Any live cache-savings check
  is **opt-in** (documented per-provider in `docs/real-model-validation.md`).
- **FR-010**: The unit MUST add **no new public package or `__all__` name**
  (the toggle is a new field on the existing `AnthropicConfig`; the breakpoint
  helper is a module-level function in `mapping.py`, which exports no `__all__`),
  so the unit-014 api-reference bijection stays green with no doc edit.

### Key Entities

- **`AnthropicConfig.prompt_caching: bool`** — the additive per-adapter toggle
  (default `True`). Off → byte-identical request.
- **`apply_prompt_caching(messages, tools)`** — a module-level helper in
  `anthropic/mapping.py` that returns new `messages`/`tools` lists with
  `cache_control` attached to the stable prefix only (the last tool definition;
  the last content block of the first message when there are ≥2 messages),
  respecting the 4-breakpoint maximum. A pure transform over the existing
  `build_messages` / `build_tools` output.

### Out of Scope

- Any change to the OpenAI/OpenRouter/Ollama/Gemini request (OpenAI-family
  caching is automatic; Gemini implicit caching is provider-managed and needs no
  request change here).
- A 1-hour TTL, pre-warming (`max_tokens: 0`), or cache-aware fork/sub-agent
  reuse — possible follow-ups, not needed for the per-turn-prefix win.
- Any new event, content block, or `TokenUsage` field; any change to the loop,
  runtime core, Tool Gateway, or Event Bus.
- Server-side or top-level "automatic" Anthropic cache placement
  (`cache_control` on `messages.create()` itself) — explicit block-level
  placement is chosen so the breakpoint sits provably on the stable prefix.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With caching ON, the assembled Anthropic request carries
  `cache_control: {"type": "ephemeral"}` on the last tool definition and on the
  last content block of the first message, with at most 4 breakpoints and none on
  the rolling last message (verified offline).
- **SC-002**: With caching OFF, the assembled Anthropic `messages`/`tools` are
  byte-identical to the existing `build_messages` / `build_tools` output
  (verified offline by equality).
- **SC-003**: The OpenAI path reports `cached_tokens` from a stub usage chunk and
  sends no cache parameter (verified offline).
- **SC-004**: The four quality gates stay green, including the unit-020 mapping
  tests (unchanged) and the unit-014 api-reference bijection (no new public
  name).
- **SC-005**: The loop, the event schema, the content model, the gateway, and
  `TokenUsage`'s shape are unchanged (no diff outside the Anthropic adapter +
  tests + docs).

## Assumptions

- **Reuse over re-implement**: the breakpoints are a pure overlay on the existing
  `build_messages` / `build_tools` output; the stream decoder and usage mapping
  are unchanged (Constitution IX).
- **Default-on is a near-pure win**: cache reads cost ~0.1x and a write ~1.25x,
  so two turns sharing a prefix already break even; agent loops re-send the
  prefix every turn. The off path is byte-identical, so default-on is safe and
  reversible.
- **No existing shape assertion blocks default-on**: the unit-020 mapping tests
  assert on `build_messages` / `build_tools` directly (kept byte-identical), and
  the integration suites build the Anthropic model with the default config but
  assert only on normalized increments/usage, never on the request kwargs shape
  — so default-on needs **no existing test update**.
- **Additive, reversible**: setting `prompt_caching=False` (or reverting the
  helper + the adapter call) restores the exact pre-caching behavior
  (Constitution X rollback).
