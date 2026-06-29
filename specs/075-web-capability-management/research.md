# Research: Web Capability Management

## Decision: Extend Inspection Into Management Additively

**Decision**: Keep the existing read-only inspection views and add explicit management flows beside them for memory, skills, MCP configuration, projects/workspaces, schedules, and model defaults.

**Rationale**: The existing inspection surface is already trusted as metadata-only and public-safe. Extending it additively gives users mutation flows without breaking users who only need read-only visibility.

**Alternatives considered**:

- Replace inspection with a settings-only surface: rejected because it would remove a stable read-only troubleshooting path.
- Build a separate admin app: rejected because it creates duplicate navigation and authorization surfaces.

## Decision: Route Mutations Through Host/Runtime Seams

**Decision**: All capability mutation requests go through host-facing methods that compose existing memory, skills, MCP, scheduler, model catalog, and session context seams.

**Rationale**: The feature must not bypass Tool Gateway ownership, Runtime Event Bus ownership, checkpoint/session boundaries, or principal scoping. Host methods give the web/API layer a narrow public-safe contract while keeping runtime ownership intact.

**Alternatives considered**:

- Let the web/API layer mutate lower-level stores directly: rejected because it blurs runtime ownership and makes scoping audits harder.
- Execute skill or MCP actions from the settings panel: rejected because this would turn configuration management into tool execution outside the Tool Gateway.

## Decision: Keep Provider Credential Entry Out Of Browser Scope

**Decision**: Model defaults can only select entries already exposed by the host-provided model catalog. Browser UI does not collect provider credentials in 075.

**Rationale**: Provider credential management needs a separate security design and user authorization. 075 only needs a default selection over already configured providers.

**Alternatives considered**:

- Add provider setup forms in the browser: rejected as out of scope and higher risk.
- Hide model defaults entirely: rejected because host-provided catalog defaults are useful and low risk.

## Decision: Principal Scoping Is Required For Every Mutable Resource

**Decision**: Memory entries, skills, MCP configurations, projects/workspaces, schedules, and defaults must be scoped to the authenticated principal or explicitly host-shared read-only resources.

**Rationale**: 074 established owner-scoped session actions. Capability mutation is higher risk and must preserve non-owner non-disclosure and deterministic behavior.

**Alternatives considered**:

- Shared global management for all users: rejected because it would make ownership unclear.
- Frontend-only hiding of non-owned items: rejected because backend enforcement is required.

## Decision: Public-Safe Problem Reporting

**Decision**: Capability management failures return fixed or sanitized messages with resource identity limited to public-safe metadata. Raw internal paths, private hostnames, stack traces, and credential-like values are never echoed.

**Rationale**: Capability records may originate from local files, external services, or user input. Error reporting must remain safe for a public repository and safe for UI display.

**Alternatives considered**:

- Display raw adapter or loader errors for debugging: rejected because they can contain private host details.
- Suppress all errors: rejected because users need actionable status.

## Decision: Schedules Use Existing Local Scheduling Semantics

**Decision**: Schedule management uses existing local schedule semantics for list, create/update, delete, enable/disable, and run-now behavior.

**Rationale**: 075 should expose management controls, not introduce a new distributed scheduler or queue. Existing semantics are enough for web parity at this stage.

**Alternatives considered**:

- Add distributed scheduling: rejected as beyond 075 and not required for web capability management.
- Defer schedules entirely: rejected because schedule management was explicitly included in the authorized 075 scope.

## Decision: Desktop Remains Compatibility-Only

**Decision**: 075 must keep desktop typecheck/tests green but does not add desktop settings UI.

**Rationale**: The parity roadmap sequences web first, then desktop cowork parity in 077. Desktop changes in 075 would increase risk and duplicate planned work.

**Alternatives considered**:

- Add desktop capability management now: rejected because it belongs to 077 after web contracts settle.
- Ignore desktop gates: rejected because desktop reuses web components and shared types.

## Decision: No ADR Required

**Decision**: 075 does not require a new ADR if implementation stays additive and preserves existing ownership boundaries.

**Rationale**: The feature exposes management over existing host/runtime seams. It does not change runtime event schemas, content model, Tool Gateway execution ownership, model provider ownership, or checkpoint semantics in a breaking way.

**Alternatives considered**:

- Require an ADR for any mutable capability UI: rejected because mutation is constrained to existing seams and later tasks can stop if a boundary change is discovered.
