# Research: Web Parity Foundation

## Decision: Add a live channel without replacing REST/SSE

**Rationale**: Existing web and desktop flows already depend on REST plus SSE behavior. 074 needs a bidirectional session path for send, abort, approval decisions, question answers, replay, and reconnect, but the safest rollout is additive. Keeping REST/SSE intact preserves compatibility while allowing the web client to opt into the new transport through a feature-local boundary.

**Alternatives considered**:

- Replace SSE with the live channel immediately. Rejected because it would create unnecessary compatibility risk for existing web/desktop tests.
- Keep only REST/SSE and add more polling endpoints. Rejected because approval/question response, abort, and reconnect coordination would remain fragmented.

## Decision: Authenticate the live channel through a short-lived ticket

**Rationale**: Browser live-channel APIs have fewer practical header options than normal REST calls. A short-lived live ticket issued by an authenticated HTTP request avoids putting long-lived bearer credentials in URLs, logs, reconnect state, or browser history. The ticket must be scoped to the principal and session and expire quickly.

**Alternatives considered**:

- Put the existing bearer token in the channel URL. Rejected because it increases leakage risk.
- Create a separate login or provider-secret flow for live channels. Rejected because browser-side secret collection is out of scope.

## Decision: Use sequence-based replay with client dedupe

**Rationale**: The existing event replay work already makes ordered session history a compatibility baseline. The live channel should accept a client-known highest sequence and replay server events after that point. The client still dedupes by stable event identity/sequence to handle race windows around disconnect and reconnect.

**Alternatives considered**:

- Replay the entire session on every reconnect with no client position. Rejected because it increases duplicate-render risk and does unnecessary work.
- Trust only client state and skip replay. Rejected because events accepted by the server during a disconnect could be lost.

## Decision: Hide transport differences behind a web-client boundary

**Rationale**: Chat state, rendering, approvals, questions, usage, message actions, and session navigation should not know whether updates arrived over REST/SSE or the live channel. A transport interface lets the implementation keep the current client as a compatibility path while adding live-channel behavior incrementally.

**Alternatives considered**:

- Thread WebSocket-specific code directly through components. Rejected because it would couple UI state to transport mechanics and make desktop reuse harder.
- Rewrite the entire web client around the live channel. Rejected because 074 is a foundation increment, not a UI rewrite.

## Decision: Extend session metadata and actions additively

**Rationale**: Existing session summaries already carry title and timestamps. 074 adds model identity, star state, fork metadata, search, bulk delete, and draft/preferred model behavior without removing existing fields or changing ownership rules. Backend metadata should remain principal-scoped, and browser-only draft state should stay local until the first send.

**Alternatives considered**:

- Create a new session store unrelated to checkpoint metadata. Rejected because it would split ownership/history state and complicate migration.
- Persist draft sessions before first send. Rejected because empty sessions pollute history and make active-session fallback harder.

## Decision: Validate web-facing types from backend-owned contract artifacts

**Rationale**: The web client needs a repeatable drift check for API responses and session events. Backend-owned schema or fixture artifacts keep the source of truth near the API/runtime boundary and let TypeScript types be generated, wrapped, or validated consistently. A lightweight repo-local workflow is preferred before introducing a large external generator dependency.

**Alternatives considered**:

- Keep handwritten TypeScript types only. Rejected because hidden drift is one of the stated risks.
- Introduce a large OpenAPI/codegen stack immediately. Rejected for 074 unless implementation proves existing tooling is insufficient.

## Decision: No ADR is required for 074

**Rationale**: The plan preserves runtime schemas, Event Bus ownership, Tool Gateway boundaries, content model, provider-secret boundaries, and existing REST/SSE public behavior. All new behavior is additive at the web/API host and web-client transport layer.

**Alternatives considered**:

- Create an ADR for every new endpoint or client type artifact. Rejected because no constitution boundary changes are proposed.
