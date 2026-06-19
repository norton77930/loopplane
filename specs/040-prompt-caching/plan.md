# Implementation Plan: Anthropic Prompt Caching (explicit cache breakpoints)

**Branch**: `040-prompt-caching` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/040-prompt-caching/spec.md`

## Summary

Add explicit Anthropic prompt-cache breakpoints so repeated agent-loop turns
re-read a stable prefix at ~0.1x instead of full price. A pure, opt-in overlay
`apply_prompt_caching(messages, tools)` in `anthropic/mapping.py` attaches
`cache_control: {"type": "ephemeral"}` to the **stable prefix only** — the last
tool definition (end of the tools segment) and the last content block of the
**first** message (a stable leading-history prefix) — never the rolling last
message, with at most 2 of the 4 allowed breakpoints. A new additive
`AnthropicConfig.prompt_caching: bool` (default **True**) gates it; the adapter
calls the helper only when the toggle is on. When off, the request is
byte-identical to today (the overlay is not applied; `build_messages` /
`build_tools` are untouched). OpenAI (and OpenRouter/Ollama, unit 035) caches
automatically with no request change — `prompt_tokens_details.cached_tokens` is
already mapped to `TokenUsage.cached_tokens`; this unit confirms + documents it.
Transparent to the loop: no event/content/usage-shape change.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new — the Anthropic SDK is already an optional
extra (`anthropic>=0.40`), imported lazily; `cache_control` is a plain dict on a
content block (no SDK type needed).

**Storage**: N/A

**Testing**: pytest (offline) — assert breakpoint placement on the assembled
request dicts (caching ON), byte-identity vs `build_messages` / `build_tools`
(caching OFF), and the OpenAI `cached_tokens` mapping from a stub usage chunk.
Mirrors the 020 offline-stub posture. Any live cache-savings check is opt-in
(`docs/real-model-validation.md` §5).

**Target Platform**: cross-platform library runtime

**Project Type**: single project — embeddable Python library/runtime

**Constraints**: no change to the loop, the runtime core, the Tool Gateway, the
Runtime Event Bus, the event schema, the content model, or `TokenUsage`'s shape;
the existing `build_messages` / `build_tools` output stays byte-identical; no new
public package/`__all__` name (the 014 bijection stays green).

**Scale/Scope**: one new module-level function + one new config field in the
Anthropic adapter package, one adapter call site, one new offline test module
(plus an OpenAI confirmation test), and docs/tracking touches.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 040).
- **II — Greenfield**: PASS (new helper written fresh; the breakpoint rules are
  re-derived for LoopPlane, not copied).
- **III — Harness before loop automation**: N/A (no loop-automation work).
- **IV — Runtime Boundary Clarity**: PASS (lives entirely at the model-boundary
  adapter; the loop, controller, dispatcher, and bus are untouched).
- **V — Tool Gateway Ownership**: N/A (no tool concern; tool *definitions* are
  marked for caching but neither resolved, authorized, nor executed here).
- **VI — Event Bus**: PASS (no event-schema change; only normalized increments
  reach the loop, via the unchanged decoder; caching is observed through the
  existing `TokenUsage.cached_tokens`, no `SCHEMA_VERSION` bump).
- **VII — Public-Safe**: PASS (a bool toggle + a public-API `cache_control`
  constant; no secret, internal path, or private name).
- **VIII — No SDK Replacement**: PASS (the SDK still enters only as a
  model-boundary adapter; the runtime core is unchanged; `cache_control` is a
  request-shape detail of that adapter).
- **IX — Reference, not clone**: PASS (the prompt-caching breakpoint placement is
  re-derived for LoopPlane's request shape — tools + a stable leading message —
  rather than copied; recorded in research.md).
- **X — Testable Evolution**: PASS (deterministic offline tests; rollback =
  `prompt_caching=False` or revert the helper + the one adapter call → exact
  pre-caching behavior).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/040-prompt-caching/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/prompt-caching.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/adapters/anthropic/
├── config.py      # MODIFY: + `prompt_caching: bool = True` field on AnthropicConfig
├── mapping.py     # MODIFY: + `apply_prompt_caching(messages, tools)` overlay helper
│                  #         (build_messages / build_tools unchanged — byte-identical)
└── adapter.py     # MODIFY: when config.prompt_caching, apply the overlay to the
                   #         assembled messages/tools (the only call site)

docs/real-model-validation.md   # MODIFY: note the opt-in cache-savings observation (§5)

tests/unit/
└── test_anthropic_caching.py   # NEW: ON placement / 4-max / not-on-tail / OFF byte-identity
tests/unit/test_openai_mapping.py  # MODIFY (or assert in place): cached_tokens mapping + no-cache-param confirm
```

**Structure Decision**: The breakpoint placement is an **opt-in overlay
function** in `anthropic/mapping.py` (not folded into `build_messages` /
`build_tools`) so the existing mapping output stays byte-identical and the
no-caching path is provably unchanged — the unit-020 mapping tests need no edit.
The toggle is a field on the existing `AnthropicConfig` (per-adapter, not the
runtime core), matching how `accepts_media` / `max_output_tokens` are carried.

## Complexity Tracking

> No Constitution Check violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
