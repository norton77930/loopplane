# Implementation Plan: Gemini Signature

**Branch**: `070-gemini-signature` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/070-gemini-signature/spec.md`

**Boundary**: settled by **[ADR 0011](../../docs/adr/0011-document-block-content-model.md)**.
This extends the ADR's content-model authorization from unit 069's `DocumentBlock` to the narrow
Gemini provider-signature metadata needed for multi-turn tool-call replay.

## Summary

Preserve Gemini's native per-function-call signature across decode, history, checkpoint, and
request-mapping boundaries. Add optional provider metadata to the normalized model/tool-call shapes,
defaulting to absent and staying out of tool input. Gemini captures and replays the real signature
when present; when absent, it keeps the existing skip-sentinel fallback. Other providers and unsigned
tool calls remain unchanged, with no Tool Gateway ownership move and no runtime event vocabulary or
schema-version change.

## Technical Context

**Language/Version**: Python 3.11+; pydantic content and model-boundary shapes.

**Primary Dependencies**: none new. Reuses existing Gemini adapter, event/checkpoint serialization,
and pytest fixtures.

**Storage**: no new storage backend. Existing checkpoint records carry content blocks and must
round-trip signature-bearing tool-call content.

**Testing**: pytest, offline. Focused tests for Gemini decode/replay, unsigned fallback,
event/checkpoint round-trip, non-Gemini unchanged behavior, and Tool Gateway input separation.

**Target Platform**: cross-platform runtime library with CLI/web/desktop/embedded host surfaces.

**Project Type**: Python runtime library with model-provider adapters.

**Performance Goals**: signature handling is local metadata copying; no network call, lookup, or
provider validation is introduced.

**Constraints**: additive; public-safe; no new dependency; no Tool Gateway state or input mutation;
no new runtime event type, termination reason, or `SCHEMA_VERSION` bump; unsigned tool-call
serialization must remain unchanged; existing Gemini fallback remains available.

**Scale/Scope**: one optional provider metadata field across the model increment/content block
handoff plus Gemini mapping/decoder support. No generic provider-signature framework beyond the
minimal shared field.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md`, this plan, and ADR 0011. PASS.
- **IV. Runtime Boundary Clarity**: The change is a model-provider continuity field carried through
  the model/content boundary and documented by ADR 0011. PASS.
- **V. Tool Gateway Ownership**: The signature stays outside tool input and gateway state; Gateway
  execution still receives only validated tool arguments. PASS.
- **VI. Runtime Event Bus Ownership**: Existing event types and schema version remain unchanged;
  tests must prove signature-bearing content round-trips. PASS.
- **VII. Public-Safe Documentation**: Docs/tests use synthetic placeholder signatures only and do
  not include provider payload dumps. PASS.
- **VIII. No SDK Replacement**: Keeps the native Gemini adapter inside LoopPlane's owned boundary;
  no agent framework adoption. PASS.
- **X. Testable Evolution**: Offline tests and rollback guidance are explicit. PASS.

**Post-design re-check**: PASS. The design remains additive, scoped, reversible, and bounded to the
existing model/content/provider-adapter boundary. Complexity Tracking is not required.

## Project Structure

### Documentation (this feature)

```text
specs/070-gemini-signature/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── gemini-signature.md
└── checklists/
    └── requirements.md

docs/adr/0011-document-block-content-model.md
```

### Source Code (repository root)

```text
src/loopplane/model/boundary.py       # MODIFIED: ToolCallRequest optional provider metadata
src/loopplane/model/content.py        # MODIFIED: ToolCallBlock optional provider metadata
src/loopplane/loop/loop.py            # MODIFIED: copy metadata from request increment to history block
src/loopplane/adapters/gemini/mapping.py  # MODIFIED: capture and replay Gemini signature
src/loopplane/adapters/openai/mapping.py  # VERIFIED: unchanged unsigned behavior
src/loopplane/adapters/anthropic/mapping.py  # VERIFIED: unchanged unsigned behavior
src/loopplane/events/envelope.py      # VERIFIED: no event vocabulary or schema change
src/loopplane/checkpoint/records.py   # VERIFIED: existing content union carries the field
docs/api-reference.md                 # MODIFIED only if public descriptions need metadata note
tests/unit/test_gemini_mapping.py     # MODIFIED: decode/replay/fallback coverage
tests/contract/test_runtime_events.py # MODIFIED: signature-bearing round-trip
tests/contract/test_checkpoint.py     # MODIFIED: signature-bearing checkpoint/rebuild
tests/integration/test_us1_tool_run.py  # MODIFIED or verified for gateway input separation
tests/unit/test_openai_mapping.py     # VERIFIED: non-Gemini unchanged behavior
tests/unit/test_anthropic_mapping.py  # VERIFIED: non-Gemini unchanged behavior
```

**Structure Decision**: Keep the change in the existing model/content/provider boundary. The Gemini
adapter owns provider-specific mapping; the Agent Loop only copies opaque metadata from
`ToolCallRequest` to `ToolCallBlock`; the Tool Gateway remains unaware.

## Complexity Tracking

> No constitution violations require justification. The content-model boundary change is ADR-backed
> and additive.
