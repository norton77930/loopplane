# Research: Web Capability Management Hardening

## Decision: Durable Capability Settings Store Under StorageConfig

**Decision**: Store user-owned mutable capability settings as public-safe JSON under `StorageConfig.root`, separate from checkpoint event/history records.

**Rationale**: Capability settings are host-owned configuration state, not session history. Reusing the existing storage root keeps persistence opt-in, durable across restarts, testable with the existing file-backed fixtures, and free of new runtime dependencies.

**Alternatives considered**:

- Extend `CheckpointStore`: rejected because capability settings are not session records and would broaden checkpoint contracts unnecessarily.
- Keep in-memory state: rejected because the feature must be product-usable and durable.
- Add a database dependency: rejected because the feature does not require one and the repo prefers additive no-new-dependency increments.

## Decision: Owner-Owned Mutable Resources Plus Shared Read-Only Host Resources

**Decision**: Model capability visibility as two scopes: user-owned mutable resources and shared host-provided read-only resources. Non-owned private resources are never disclosed.

**Rationale**: This preserves the current host inspection value while closing the 075 scoping gap. Users can identify shared capabilities without being able to mutate host-owned configuration, and owner-created resources remain private and usable only by that principal.

**Alternatives considered**:

- Make every resource private: rejected because host-provided skills, tools, and memory metadata are useful inspection signals.
- Treat the web host as single-user: rejected because prior web units already established principal-scoped sessions.

## Decision: Scoped Runtime Activation Through Existing Boundaries

**Decision**: User-created memory, skills, and MCP configurations become available to the owner's later eligible sessions through principal-aware host/controller/gateway seams.

**Rationale**: A settings surface is not complete if it only stores data. Runtime activation must be owner-scoped, fail-closed for non-owners, and still route all tool resolution/execution through the Tool Gateway.

**Alternatives considered**:

- Manage settings only, apply on host restart: rejected because it is surprising and fails the product-usable goal.
- Apply changes mid-turn: rejected because it makes the active turn unstable and harder to test.
- Expose managed tools outside the gateway: rejected by Constitution Principle V.

## Decision: Narrow Tool Gateway Scoped-Adapter Extension

**Decision**: Add a narrow gateway-owned way to register, replace, describe, and shut down managed adapters by owner/scope for skills and MCP. Existing shared adapter registration remains unchanged.

**Rationale**: MCP reconnect must refresh available tools without bypassing gateway ownership. Keeping scoped adapter lifecycle inside the gateway maintains the single chokepoint for resolution, authorization, execution, timeout, and error normalization.

**Alternatives considered**:

- Rebuild the whole host on reconnect: rejected because it is disruptive and does not fit a live settings surface.
- Only test MCP connectivity without updating tools: rejected because users expect reconnect to affect capability availability.
- Add unregister behavior outside the gateway: rejected because it blurs Tool Gateway ownership.

## Decision: Additive API Contract

**Decision**: Preserve existing 075 endpoints and response compatibility while adding fields and detail/action routes needed for full management.

**Rationale**: Existing 075 tests and clients remain useful regression coverage. Additive contracts let the new settings view use richer behavior without breaking previous inspection or capability client assumptions.

**Alternatives considered**:

- Replace capability endpoints with a new API: rejected because it would create avoidable compatibility churn.
- UI-only wrappers over existing endpoints: rejected because backend scoping, durability, and reconnect gaps cannot be solved in the UI.

## Decision: Independent Settings View

**Decision**: Add an independent capability settings view launched from the app shell/header, while keeping the inspection panel metadata-only.

**Rationale**: Full CRUD, import, reconnect, bind, run-now, enable/disable, and delete confirmations need more space than the inspection sidebar. Keeping inspection read-only preserves the 027/075 compatibility story.

**Alternatives considered**:

- Keep all management in the inspection tab: rejected because the workflow becomes cramped and mixes read-only inspection with mutation.
- Use only modals: rejected because multi-section settings flows need persistent lists and status refresh.

## Decision: Host-Controlled Mutation Gate

**Decision**: Add a host-controlled gate that disables mutation actions while preserving read-only inspection/listing and chat/session behavior.

**Rationale**: The gate provides rollback and operational safety without reverting the entire web app. It also supports hosts that expose inspection but do not configure durable capability storage.

**Alternatives considered**:

- Hide only the frontend entry point: rejected because direct API calls would still mutate.
- No gate: rejected because rollback guidance would rely only on code revert.

## Decision: Default-Off Capability Configuration

**Decision**: Add an optional host capability-management configuration. Mutations and owner-scoped runtime activation are independently explicit and default off; durable records remain readable when either gate is disabled.

**Rationale**: This preserves byte-identical default runtime behavior, provides an operational rollback path, and avoids making stored settings disappear when mutation or activation is disabled.

## Decision: Policy-Gated Network MCP Only

**Decision**: Browser-managed MCP supports HTTP, SSE, and WebSocket only after a host-injected endpoint policy approves the URL. The policy is default-deny. Browser-managed stdio is refused and command/args are not persisted; host-configured shared stdio remains read-only.

**Rationale**: Real reconnect otherwise turns a settings form into arbitrary local process execution or an unrestricted server-side request primitive.

## Decision: Injected Schedule Run-Now

**Decision**: Add an optional schedule instruction and dispatch run-now through a host-injected async runner. Disabled, instruction-less, non-owned, and runner-less schedules are refused. Periodic orchestration remains in the Phase-3 scheduler.

**Rationale**: The host/web layer cannot import the Phase-3 scheduler, and the existing 075 schedule record has no executable work definition.
