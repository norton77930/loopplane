# Research: Model-Native Structured Output

No open `NEEDS CLARIFICATION`. The decisions below resolve the boundary question raised by
spec FR-007 and fix the v1 provider scope.

## Decision 1 — How the per-request schema reaches the adapter (the boundary question)

**Decision**: Add an **optional, defaulted** field `output_schema: dict[str, object] | None
= None` to the existing `ModelRequest` pydantic model in `model/boundary.py`. The loop
already builds and forwards a `ModelRequest` to `stream_turn(request)`, so the schema rides
that existing per-call object.

**Rationale**: The schema is per-request (each run may differ), so it must reach the adapter
per call — not via adapter construction. `stream_turn(request: ModelRequest)` takes a
structured request object, so an **optional new field is additive and backward-compatible**:
every existing `ModelRequest(context=…, tools=…, limits=…)` construction and every
`stream_turn` implementation keeps working, and `None` is byte-identical to today. This is
the same additive move as unit-034's `ToolDescriptor.network` field — **no `stream_turn`
signature change, no breaking 001/020 contract change, no ADR** (board §9.5 does not apply).

**Alternatives considered**: a new `stream_turn` parameter (rejected — changes the Protocol
signature = a breaking contract change / §9.5 stop); carrying the schema in the content model
(rejected — it is request configuration, not conversation content; would touch the content
model, VI); adapter-construction config (rejected — schema is per-request, not per-model).

## Decision 2 — Capability negotiation & graceful degradation

**Decision**: Add a duck-typed `supports_structured_output(model)` probe + a
`StructuredOutputModel` Protocol in `model/capabilities.py`, mirroring unit-036
`accepts_media`. Each adapter opts in via a `supports_structured_output()` method backed by a
config flag. The **web/API layer** (the model-selecting boundary, 028) rejects a schema sent
to a non-supporting model with a clear normalized error (HTTP 400), and `/v1/models`
advertises the capability.

**Rationale**: Reuses the proven 036 negotiation pattern, keeps the `ModelBoundary` Protocol
unchanged (still `stream_turn` + `context_capacity`), and places negotiation at the boundary
that owns model selection (Constitution IV), not in the loop.

**Alternatives considered**: silently dropping the schema (rejected — misleads the caller,
FR-004); best-effort prompt-injection on non-supporting providers (rejected — no conformance
guarantee; out of scope).

## Decision 3 — Provider mapping & v1 scope

**Decision**: v1 maps native structured output for the **OpenAI chat-completions** path —
shared by the `openai`, `openrouter`, and `ollama` adapters via `openai_compat` — using
`response_format: {"type": "json_schema", "json_schema": {"name", "schema", "strict": true}}`
when `request.output_schema` is set (omitted entirely when `None`). Capability flags:
`openai` = `True`, `openrouter` = `True`, `ollama` = configurable (**default `False`** —
support varies by local model), `anthropic` = `False`, `gemini` = `False`. **Anthropic and
Gemini native structured output are deferred** (they degrade gracefully via the `False` flag).

**Rationale**: `response_format` json_schema is a clean, well-defined OpenAI-family API and
covers the most-used providers in one shared mapping, closing G3 for them additively. Native
Anthropic (tool-use / its structured-output API) and Gemini (`response_schema`) mappings add
provider-specific complexity; deferring them keeps v1 bounded while the capability flag makes
the degradation honest. The deferral is recorded here and in the board.

**Alternatives considered**: mapping all five providers now (rejected — scope/complexity for
a Tier-1 unit; Anthropic/Gemini mappings differ enough to warrant their own follow-up).

## Decision 4 — Verification reuses unit-005

**Decision**: Conformance is checked with the existing unit-005 JSON-schema validator pack;
no new validation engine or dependency. Used in tests and available to callers/loops.

**Rationale**: Constitution X (reuse-first); the pack already validates JSON against a schema.

## Decision 5 — Malformed schema is rejected fail-fast

**Decision**: A malformed/invalid supplied schema is rejected at request time (web/API edge)
before any model call, with a clear normalized error (FR-008).

**Rationale**: Fail-closed mirrors the other boundary validations (036 oversized-image 413,
039 invalid-rule config error).
