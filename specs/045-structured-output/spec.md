# Feature Specification: Model-Native Structured Output

**Feature Branch**: `045-structured-output`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Model-native structured output — let a caller request a JSON-schema-constrained response (`response_format`), mapped to provider-native structured output, with graceful degradation when a provider lacks native support. Unit 045, Tier-1; closes gap G3. Additive; reuses the packs JSON-schema validators for verification; no event-schema change."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Host constrains a response to a schema (Priority: P1)

A host supplies a JSON schema with a run and asks the agent for a final response that
conforms to it (for example, an object with specific fields). When the selected model
provider supports native structured output, the provider is instructed to emit output
matching the schema, so the host receives machine-parseable, schema-shaped output.

**Why this priority**: This is the core value — reliable, schema-shaped output is what the
reference agent harnesses expose (gap G3) and what callers need to build on the agent
programmatically.

**Independent Test**: Run with a supported provider and a simple schema; confirm the final
response parses and validates against the schema. Delivers the structured-output value on
its own.

**Acceptance Scenarios**:

1. **Given** a run on a provider that supports native structured output, **When** the host
   supplies a JSON schema, **Then** the provider request is configured to produce output
   conforming to that schema and the response validates against it.
2. **Given** a run with **no** schema supplied, **When** the run proceeds, **Then**
   behavior is identical to today (the feature is off by default).

---

### User Story 2 - Graceful degradation on unsupported providers (Priority: P2)

A host supplies a schema but the selected provider does not support native structured
output. The system reports this clearly rather than silently ignoring the schema or
producing unconstrained output presented as structured.

**Why this priority**: Honesty and safety — a caller relying on schema conformance must not
be misled when the provider cannot guarantee it.

**Independent Test**: Run with a schema on a provider whose capability flag is false;
confirm a clear, normalized error is returned and no run produces falsely-"structured"
output.

**Acceptance Scenarios**:

1. **Given** a provider that does not support native structured output, **When** the host
   supplies a schema, **Then** the request is rejected with a clear, normalized error at the
   model-selecting boundary (no leaked internals).
2. **Given** the model catalog (`/v1/models` or equivalent), **When** the host inspects a
   model, **Then** the model advertises whether it supports structured output.

---

### User Story 3 - The output is verifiable against the schema (Priority: P3)

The schema-shaped output can be validated against the supplied schema so a caller (or the
loop) has a checkable guarantee, reusing the existing validator packs.

**Why this priority**: Closes the loop — structured output is most useful when its
conformance is verifiable with existing tooling.

**Independent Test**: Feed a structured response and the schema to the existing JSON-schema
validator pack; confirm conforming output passes and non-conforming output fails.

**Acceptance Scenarios**:

1. **Given** a structured response and its schema, **When** validated with the existing
   JSON-schema validator pack, **Then** conforming output passes and non-conforming output
   fails with a diagnostic.

---

### Edge Cases

- **Invalid/malformed schema supplied**: rejected with a clear error at request time
  (fail-fast), before any model call.
- **Provider claims support but returns non-conforming output**: surfaced via validation
  (US3); the run does not crash.
- **No schema**: the byte-identical default path (FR-006).
- **Empty/trivial schema**: treated per the schema validator's rules; no special-casing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A host MUST be able to supply a JSON schema with a run to request that the
  model's final response conform to it; supplying none leaves the run unconstrained.
- **FR-002**: When a schema is supplied and the selected provider supports native structured
  output, the system MUST configure the provider request to produce output conforming to the
  schema.
- **FR-003**: The system MUST expose a per-provider/per-model capability signal indicating
  whether native structured output is supported (mirroring the unit-036 `accepts_media`
  capability-negotiation pattern), surfaced through the model catalog.
- **FR-004**: When the selected provider does NOT support native structured output and a
  schema is supplied, the system MUST reject the request with a clear, normalized error at
  the model-selecting boundary (no silent drop, no falsely-structured output, no leaked
  internals).
- **FR-005**: A structured response MUST be verifiable against the supplied schema by reusing
  the existing JSON-schema validator pack (unit 005); no new validation engine.
- **FR-006**: With no schema supplied, behavior MUST be byte-identical to today (the feature
  is additive and off by default).
- **FR-007**: The feature MUST be additive: no change to the runtime event schema or
  `SCHEMA_VERSION`, and no change to the shared content model. The mechanism by which the
  schema reaches the adapter MUST be resolved in planning; if it cannot be done without
  changing an existing public contract (e.g., the model boundary), that boundary crossing
  MUST be recorded in an ADR and gated on approval rather than introduced silently.
- **FR-008**: A malformed or invalid supplied schema MUST be rejected with a clear error at
  request time (fail-fast), before any model call.

### Key Entities *(include if feature involves data)*

- **Output schema**: a caller-provided JSON schema describing the desired shape of the
  model's final response.
- **Structured response**: the model's final response, intended to conform to the output
  schema; verifiable against it.
- **Structured-output capability**: a per-model boolean signal (supported / not) used for
  negotiation and graceful degradation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a supporting provider with a supplied schema, the final response validates
  against the schema in the happy path.
- **SC-002**: On a non-supporting provider with a supplied schema, the request is rejected
  with a clear error in 100% of cases (never falsely-structured output).
- **SC-003**: Runs with no schema are unaffected — the existing test suite passes unchanged
  and no event-schema or content-model change is introduced.
- **SC-004**: A malformed schema is rejected at request time in 100% of cases, before any
  model call.

## Assumptions

- "Structured output" means provider-native constrained generation (e.g., OpenAI
  `response_format` json_schema; Anthropic structured/tool-use output; Gemini response
  schema). The exact per-provider mapping is a planning/implementation concern.
- The additive mechanism is expected to mirror unit 036: a duck-typed capability probe plus
  an optional, defaulted configuration — not a required new method on the model-boundary
  Protocol. Planning confirms whether this holds; if a public-contract change is unavoidable,
  an ADR is written and approval sought (FR-007).
- Validation reuses the unit-005 JSON-schema validator pack; no new validation dependency.
- Out of scope for this unit: streaming partial structured output; enforcing the schema
  across multiple turns; a best-effort prompt-injection fallback for non-supporting
  providers; structured output for tool arguments (already provider-native).
- Per Constitution IX, the concept is borrowed from the reference harnesses but re-derived
  through this spec.
