# Implementation Plan: Model-Native Structured Output

**Branch**: `045-structured-output` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/045-structured-output/spec.md`

## Summary

Let a host supply a JSON schema with a run so the model's final response is constrained to
it on providers that support native structured output. The schema is carried **per-call** on
an additive, optional `ModelRequest.output_schema` field (default `None` → byte-identical to
today). The OpenAI chat-completions mapping (shared by the `openai`, `openrouter`, and
`ollama` adapters) maps it to `response_format: {type: json_schema, …}`. A duck-typed
`supports_structured_output(model)` capability probe (mirroring unit-036 `accepts_media`)
drives **graceful degradation**: the web/API layer rejects a schema for a non-supporting
model with a clear error, and `/v1/models` advertises the capability. Verification reuses the
unit-005 JSON-schema validator pack. **No `stream_turn` signature change, no event-schema /
`SCHEMA_VERSION` / content-model change, no new dependency, no ADR** — additive throughout
(the `ModelRequest` field addition mirrors unit-034's additive `ToolDescriptor.network`).

## Technical Context

**Language/Version**: Python 3.11+ (`loopplane`)

**Primary Dependencies**: none new (reuses the existing `openai` extra mapping, pydantic
models, and the unit-005 `packs` JSON-schema validator)

**Storage**: N/A (the schema is per-request input; no persistence)

**Testing**: pytest, offline (a fake/stub OpenAI client asserts the `response_format`
wiring; capability + webapi-rejection + validation tests)

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; optional field default `None` is byte-identical;
reject (not silently drop) on a non-supporting model; no ADR (additive field + duck-typed
probe, per the 034/036 precedent)

**Scale/Scope**: one additive `ModelRequest` field + one capability probe + the OpenAI
mapping + per-adapter capability flags + a thin web/API request field & rejection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008. ✅
- **IV. Runtime Boundary Clarity**: Capability *negotiation* (rejecting a schema for a
  text-only-of-structured model) lives at the model-selecting web/API boundary (028), not in
  the Agent Loop — exactly as 036 placed `accepts_media`. The loop just forwards
  `request.output_schema` to the adapter. ✅
- **V. Tool Gateway Ownership**: Untouched (no tool change). ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change; the
  added `ModelRequest.output_schema` is a model-boundary *request* field (like 034's
  `ToolDescriptor.network`), not an event. ✅
- **VIII. No SDK Replacement**: Providers' own structured-output features are used through the
  existing adapter mapping; no framework added. ✅
- **IX. Reference, Not Clone**: Re-derived; the OpenAI `response_format` shape is the
  provider's public API, not copied harness code. ✅
- **X. Testable Evolution**: Additive, default-`None` byte-identical, reversible (drop the
  field + probe + mapping branch); offline-tested. ✅

**Result**: PASS — no violations; no ADR required (additive field + duck-typed probe, per the
unit-034 `ToolDescriptor.network` / unit-036 `accepts_media` precedent). Complexity Tracking
not required.

> Boundary-crossing check (spec FR-007 / board §9.5): adding an **optional, defaulted** field
> to the `ModelRequest` pydantic model is backward-compatible — every existing
> `ModelRequest(context=…, tools=…, limits=…)` construction and every `stream_turn`
> implementation keeps working unchanged. This is an additive extension, **not** a breaking
> change to the 001/020 public contract, so no §9.5 stop and no ADR (matching 034).

## Project Structure

### Documentation (this feature)

```text
specs/045-structured-output/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/structured-output.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/model/
├── boundary.py          # MODIFIED: add optional ModelRequest.output_schema field
└── capabilities.py      # MODIFIED: add StructuredOutputModel Protocol + supports_structured_output(model)

src/loopplane/adapters/
├── openai/mapping.py    # MODIFIED: map request.output_schema -> response_format (json_schema)
├── openai/adapter.py    # MODIFIED: OpenAIConfig.supports_structured_output flag + method
└── openai_compat/       # MODIFIED: openrouter (True) / ollama (configurable, default False) flags

src/loopplane/webapi/    # MODIFIED: optional RunRequest.output_schema; thread to ModelRequest;
                         #   reject on a non-supporting model (clear error) + malformed schema;
                         #   /v1/models advertises supports_structured_output

tests/unit/test_structured_output.py   # NEW: mapping, capability probe, webapi rejection,
                                        #   malformed-schema rejection, default-None identity
```

**Structure Decision**: Single-project additive change centered on the model boundary +
the OpenAI mapping + the web/API edge. v1 delivers native structured output for the
**OpenAI-family** (openai / openrouter / ollama, which share the chat-completions mapping);
**Anthropic and Gemini native structured output are deferred** (their capability flag is
`False`, so they degrade gracefully) and recorded as a follow-up.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
