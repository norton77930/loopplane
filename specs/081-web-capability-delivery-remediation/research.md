# Research: Web Capability Delivery Remediation

## Decision 1: Validate browser-managed MCP endpoints structurally before policy evaluation

**Decision**: Add one side-effect-free structural validator in the host capability domain. HTTP and SSE accept `http`/`https`; WebSocket accepts `ws`/`wss`. Reject stdio, empty endpoint or host, userinfo, query, fragment, incompatible scheme, and invalid port syntax. Call it from managed-MCP upsert, reconnect/activation, and capability-store writes. The host endpoint policy remains a separate principal-aware, default-deny check after structural validation.

**Rationale**: Current manager paths only check non-empty values and policy approval, while the store can be called directly with unstructured MCP records. A shared structural rule closes browser, domain, reconnect, legacy-activation, and persistence bypasses without moving host policy into persistence.

**Alternatives considered**:

- Request-model-only validation: rejected because direct manager/store callers and legacy records bypass it.
- Strict typed MCP persistence migration: rejected because it expands the remediation into schema migration and could make entire legacy documents unreadable.
- Reusing display-oriented URL sanitization: rejected because display labels do not enforce endpoint admissibility.
- HTTPS-only policy: rejected; endpoint transport security remains host-policy-owned and the current contract permits approved HTTP.

## Decision 2: Preserve HTTP envelopes while making public host update/delete methods async

**Decision**: Convert managed-MCP upsert and delete methods across `CapabilityManager` and `LoopPlaneHost` to async and await them from existing async Web routes. HTTP paths, request bodies, status/result enums, and JSON response envelopes remain unchanged. The maintainer approved this Python host API contract change on 2026-07-27.

**Rationale**: Immediate resolution removal and lease-safe exactly-once shutdown require awaiting `ToolGateway.remove_scoped_adapter()`. Hiding that lifecycle in background work would make completion and error handling nondeterministic.

**Alternatives considered**:

- Preserve synchronous methods and defer cleanup until next activation: rejected because it leaves a stale-resolution window and violates FR-007–FR-009.
- Add parallel async methods while retaining synchronous mutation semantics: rejected because two lifecycle paths would drift and the old path would remain unsafe.
- Add new Gateway SPI operations: rejected because the existing scoped-adapter lifecycle already provides the required behavior.

## Decision 3: Reuse ToolGateway retirement primitives without changing Gateway semantics

**Decision**: Add one private manager helper that removes the owner-scoped adapter and updates `_active_mcp_ids`. Use it after successful update/delete and on every terminal reconnect failure. Successful reconnect continues to use `replace_scoped_adapter()`. Treat every non-connected stored status as inactive during principal activation.

**Rationale**: `ToolGateway` already removes registry visibility before awaiting shutdown, retains leased invocations, and shuts down a retired adapter exactly once after final release.

**Alternatives considered**:

- Modify Gateway stage order or lease accounting: rejected as unnecessary and boundary-sensitive.
- Resolve or close adapters directly from the host: rejected because tool lifecycle ownership belongs to the Gateway.

## Decision 4: Supply allowed workspace contexts through an optional host-owned provider

**Decision**: Add a callable Protocol that accepts one principal ID and returns allowed `WorkspaceContext` values. Add it to `CapabilityManagementConfig` with default `None`. The manager reconstructs safe `shared_read_only` projections and never persists provider values into per-principal capability JSON.

**Rationale**: This fulfills the frozen 076 owned-or-allowed context contract while preserving principal scoping and owner-only byte identity when the provider is absent.

**Collision and failure rules**:

- Duplicate IDs from the provider are excluded.
- Any owner/provider ID collision is excluded from list/get/bind.
- Provider exceptions or invalid records fail closed for the allowed contribution while owner records remain available.
- Unknown, unauthorized, collided, and cross-principal context access all use the existing non-disclosing not-found path.

**Alternatives considered**:

- Copy allowed contexts into each principal's store: rejected because read-only host state would become mutable user-owned durability.
- Owner-wins or provider-wins collision handling: rejected because source ambiguity could authorize the wrong context.
- Add new Web routes: rejected because current list/detail/bind routes already carry principal and session ownership.

## Decision 5: Keep existing HTTP detail shapes and sanitize shared projections

**Decision**: Do not make existing detail fields optional and do not change route schemas. Shared memory detail returns safe metadata and bounded snippet while its full-content field is empty; shared skill detail returns safe metadata while instructions are empty; shared MCP detail keeps URL absent/null and raw failures excluded. Owner details retain their existing complete shape.

**Rationale**: This closes disclosure risks without an outward HTTP/generated-type change. The UI uses scope and actions to select safe read-only presentation and never displays owner-only fields for shared resources.

**Alternatives considered**:

- Make detail fields optional or add owner/shared unions: rejected for 081 because it changes the outward HTTP contract and generated types without being necessary to meet the security outcome.
- Reuse editable forms for shared open: rejected because it exposes owner-only fields and presents false mutation affordances.

## Decision 6: Make projected actions the UI interaction authority

**Decision**: Add one reusable read-only capability detail component under the existing settings modules. Show Open, Bind, Update, Delete, or Reconnect only when the projection includes that action. Shared resources can expose Open, and allowed contexts can expose Bind when the mutation gate permits it. Remove the legacy `CapabilitySettings.tsx` surface and its dedicated tests.

**Rationale**: Current modules special-case shared scope and treat Open as loading an editor. Action-driven details align all capability types, preserve 080 layout/accessibility patterns, and avoid future scope-label authorization logic.

**Alternatives considered**:

- Add separate shared branches in four settings modules: rejected as duplicated and likely to drift.
- Leave the unused legacy component: rejected because it retains a second unsupported mutation surface.

## Decision 7: Treat 081 as remediation with frozen 076/080 history

**Decision**: Record requirements, tasks, verification, rollback, and synchronization under 081. Do not edit 076/080 spec or tasks. Maintain explicit 076, 080, 081, and local/unknown ownership buckets; `.superpowers/**` and unclassified changes are excluded from delivery.

**Rationale**: Project alignment rules require a remediation unit for batched cross-boundary fixes found after Verified status and prohibit retro-editing frozen artifacts.

**Alternatives considered**:

- Reopen 076 or 080 tasks: rejected by the Spec Kit alignment rules.
- Blind directory staging: rejected because the working tree mixes product changes with local workflow artifacts.

## ADR and approval conclusion

No new ADR is required because 081 preserves runtime ownership, Gateway SPI/stage order, Event Bus and checkpoint contracts, dependencies, schemas, and defaults. The public Python host sync-to-async change was the only newly discovered human gate and was explicitly approved on 2026-07-27. Any later proposal to change HTTP schemas, persistence schema, defaults, dependencies, Gateway SPI, or runtime/event/checkpoint boundaries must stop for a new human gate and possibly an ADR.
