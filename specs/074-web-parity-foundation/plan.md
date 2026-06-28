# Implementation Plan: Web Parity Foundation

**Branch**: `074-web-parity-foundation` (main-only autopilot) | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/074-web-parity-foundation/spec.md`

## Summary

Add the web parity foundation needed before capability management and deeper agent controls: an additive bidirectional live session channel, a web-client transport boundary that lets REST/SSE and the live channel coexist, session-management metadata/actions for draft, model preference, star, fork, search, and bulk delete, plus repeatable contract/type validation for web-facing API and event shapes.

The implementation must preserve existing REST/SSE flows, desktop compatibility, runtime event semantics, Tool Gateway ownership, principal scoping, and provider-secret boundaries. The feature is behavior parity only; external reference apps may inform desired behavior but no implementation code or private material is copied.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.6; React 18

**Primary Dependencies**: Existing FastAPI/AnyIO/Pydantic web host; existing React/Vite/Vitest web app; existing checkpoint, event replay, host, model catalog, approval/question, cancellation, and upload seams. No required new runtime dependency is planned for 074.

**Storage**: Existing checkpoint stores for session metadata/history, event replay store when configured, and browser storage for local draft/model preference state.

**Testing**: pytest for backend/unit/integration/contract coverage; Vitest, TypeScript strict checks, and Vite build for web coverage; existing desktop TypeScript/Vitest gates for compatibility.

**Target Platform**: Browser SPA over the LoopPlane web/API host. Desktop remains compatible through existing web state/components until unit 077 intentionally expands desktop behavior.

**Project Type**: Full-stack web application increment over an existing Python runtime and TypeScript SPA.

**Performance Goals**: Reconnect restores a typical active session within 2 seconds in automated tests; search and bulk-delete paths are bounded to owned sessions and do not scan unrelated principals.

**Constraints**: Additive only; preserve existing `/v1` REST/SSE behavior; preserve normalized runtime event ownership; preserve Tool Gateway boundaries; preserve principal scoping; do not collect provider secrets in browser; do not modify raw `openspec/`; do not copy private/reference implementation code.

**Scale/Scope**: One roadmap unit covering live web transport foundation, session-management groundwork, and contract/type validation. Capability management, plan/permission/budget controls, desktop cowork features, and CLI/remote parity are deferred to units 075-078.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --------- | ------ | ----- |
| I. Spec-First Development | PASS | Work is scoped by `spec.md`, this plan, and later `tasks.md`. |
| II. Greenfield Implementation | PASS | Reference apps are behavior references only; implementation is re-derived. |
| IV. Runtime Boundary Clarity | PASS | Live transport adapts web host/session behavior without moving runtime ownership. |
| V. Tool Gateway Ownership | PASS | Tool execution and permission checks remain behind the existing gateway. |
| VI. Runtime Event Bus Ownership | PASS | UI consumes normalized session events; no frontend-specific events from the Agent Loop. |
| VII. Public-Safe Documentation | PASS | No private paths, raw reference content, credentials, tokens, or secrets may enter artifacts. |
| VIII. No SDK Replacement | PASS | No external agent framework replaces LoopPlane runtime ownership. |
| IX. Reference, Not Clone | PASS | Parity is described as behavior and mechanism, not code cloning. |
| X. Testable Evolution | PASS | Contract, unit, integration, web, desktop, validation, and rollback gates are required. |

Post-design re-check: PASS. Research and contracts keep changes additive, boundary-preserving, testable, and reversible.

## Project Structure

### Documentation (this feature)

```text
specs/074-web-parity-foundation/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- live-session-channel.md
|   |-- session-management.md
|   `-- type-artifacts.md
`-- tasks.md                 # Created by /speckit.tasks, not this step
```

### Source Code (repository root)

```text
src/loopplane/
|-- checkpoint/
|   |-- base.py
|   |-- file.py
|   `-- sqlite.py
|-- controller/controller.py
|-- host/host.py
`-- webapi/
    |-- app.py
    |-- models.py
    |-- sessions.py
    `-- contract_types.py

apps/web/src/
|-- api/
|   |-- client.ts
|   |-- generated.ts
|   |-- liveTransport.ts
|   |-- restTransport.ts
|   `-- transport.ts
|-- components/
|-- state/
|   |-- chat.ts
|   `-- sessions.ts
`-- __tests__/

apps/desktop/
|-- electron/
`-- src/

tests/
|-- contract/
|-- integration/
`-- unit/
```

**Structure Decision**: 074 is a full-stack web increment. Backend changes stay in existing host/webapi/checkpoint seams; frontend changes stay in the web app API/state/component layers; desktop source is touched only if compatibility tests require a minimal adapter update. `tasks.md` will decide exact file edits after contracts are generated.

## Phase 0: Research Output

Research decisions are recorded in [research.md](research.md):

- Add live channel without replacing REST/SSE.
- Authenticate live channel through a short-lived ticket derived from existing HTTP auth.
- Use sequence-based replay and client dedupe for reconnect.
- Keep live/rest behavior behind a web transport boundary.
- Extend session metadata/actions additively.
- Validate web-facing types from backend-owned contract artifacts.
- No ADR is required for this unit because public runtime boundaries are preserved.

## Phase 1: Design Output

- Data model: [data-model.md](data-model.md)
- Live channel contract: [contracts/live-session-channel.md](contracts/live-session-channel.md)
- Session management contract: [contracts/session-management.md](contracts/session-management.md)
- Type artifact contract: [contracts/type-artifacts.md](contracts/type-artifacts.md)
- Validation guide: [quickstart.md](quickstart.md)

## Complexity Tracking

No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
