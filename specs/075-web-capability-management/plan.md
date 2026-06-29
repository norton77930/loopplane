# Implementation Plan: Web Capability Management

**Branch**: `075-web-capability-management` (main-only autopilot) | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/075-web-capability-management/spec.md`

## Summary

Expand the existing web inspection experience into an additive capability management surface for memory, skills, MCP configuration, project/workspace context, schedules, and host-provided model defaults. The work must preserve 074 chat/session behavior, principal scoping, Tool Gateway ownership, Runtime Event Bus ownership, public-safe diagnostics, and the browser-side provider credential boundary.

The implementation approach is to add host/web management seams over existing capability layers, expose additive web/API management endpoints, and extend the web settings UI with mutation flows that remain principal-scoped and public-safe. Desktop remains compatibility-only until 077.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.6; React 18

**Primary Dependencies**: Existing FastAPI/AnyIO/Pydantic web host; existing host inspection/query seams; existing skills, MCP, memory/recall, scheduler, model catalog, session, and 074 transport/session-management surfaces. No required new runtime dependency is planned for 075.

**Storage**: Existing checkpoint/session state, existing memory/skills/MCP/scheduler persistence seams where present, and browser local state only for UI preferences. No browser-side provider credential storage.

**Testing**: pytest for backend unit/integration/contract coverage; Vitest, TypeScript strict checks, and Vite build for web coverage; desktop TypeScript/Vitest gates for compatibility.

**Target Platform**: Browser SPA over the LoopPlane web/API host. Desktop remains compatible through the existing shared web state/components until 077.

**Project Type**: Full-stack web application increment over the existing Python runtime and TypeScript SPA.

**Performance Goals**: Capability list views load within 2 seconds in automated tests using representative datasets; mutation flows settle into a visible success or public-safe error state without page reload.

**Constraints**: Additive only; preserve 074 REST/SSE/live chat behavior; preserve Tool Gateway ownership for tool execution; preserve Runtime Event Bus ownership for normalized session events; preserve principal scoping; do not collect provider credentials in the browser; do not modify raw `openspec/`; do not copy reference implementation code or private material.

**Scale/Scope**: One roadmap unit covering web capability management for memory, skills, MCP config, project/workspace context, schedules, and model defaults. Plan/permission/budget controls, workspace file/artifact panels, follow-up suggestions, desktop cowork parity, and CLI/remote parity are deferred to 076-078.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --------- | ------ | ----- |
| I. Spec-First Development | PASS | Work is scoped by `spec.md`, this plan, later tasks, and the generated contracts. |
| II. Greenfield Implementation | PASS | Claude Code and Orion remain behavior references only; implementation is re-derived. |
| IV. Runtime Boundary Clarity | PASS | Capability management composes existing host/runtime seams and does not move component ownership. |
| V. Tool Gateway Ownership | PASS | Tool execution remains behind the Tool Gateway; MCP management does not execute tools directly. |
| VI. Runtime Event Bus Ownership | PASS | UI capability settings do not change normalized runtime event semantics. |
| VII. Public-Safe Documentation | PASS | Artifacts avoid private paths, private names, raw reference content, and credential-like values. |
| VIII. No SDK Replacement | PASS | No external agent framework replaces LoopPlane runtime ownership. |
| IX. Reference, Not Clone | PASS | Parity is expressed as behavior and mechanism, not copied implementation. |
| X. Testable Evolution | PASS | Contract, backend, web, desktop compatibility, rollback, and public-safety validation are required. |

Post-design re-check: PASS. Research and contracts keep changes additive, principal-scoped, boundary-preserving, testable, and reversible.

## Project Structure

### Documentation (this feature)

```text
specs/075-web-capability-management/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- capability-management.md
|   |-- project-workspace-context.md
|   `-- schedules-and-model-defaults.md
`-- tasks.md                 # Created by /speckit.tasks, not this step
```

### Source Code (repository root)

```text
src/loopplane/
|-- host/
|   `-- host.py              # additive capability management methods
|-- skills/                  # existing skill loading/import seams
|-- adapters/mcp/            # existing MCP registry/config seams
|-- memory/                  # existing memory/knowledge seams
|-- scheduling/              # existing schedule seams
`-- webapi/
    |-- app.py               # additive management routes
    |-- models.py            # metadata-only request/response views
    `-- contract_types.py    # update if web type artifacts are needed

apps/web/src/
|-- api/
|   |-- client.ts
|   |-- types.ts
|   `-- generated.ts
|-- components/
|   `-- InspectionPanel.tsx  # expand from read-only to managed settings
|-- state/
`-- __tests__/

apps/desktop/
`-- src/                     # compatibility tests only unless needed

tests/
|-- contract/
|-- integration/
`-- unit/
```

**Structure Decision**: 075 is a full-stack web increment. Backend changes stay in existing host/webapi/capability seams; frontend changes stay in the web app API/state/component layers; desktop source is touched only for compatibility tests or a minimal shared-type adapter. `tasks.md` will decide exact file edits after contracts are generated.

## Phase 0: Research Output

Research decisions are recorded in [research.md](research.md):

- Extend read-only inspection into additive management rather than replacing it.
- Keep browser-side provider credential collection out of scope.
- Route capability mutations through host/runtime seams instead of bypassing ownership boundaries.
- Preserve principal scoping and public-safe error behavior for every mutable resource.
- Use host-provided model catalog entries only for model defaults.
- Preserve 074 chat/session and desktop compatibility gates.
- No ADR is required for this unit because runtime ownership boundaries are preserved.

## Phase 1: Design Output

- Data model: [data-model.md](data-model.md)
- Capability management contract: [contracts/capability-management.md](contracts/capability-management.md)
- Project/workspace context contract: [contracts/project-workspace-context.md](contracts/project-workspace-context.md)
- Schedules and model defaults contract: [contracts/schedules-and-model-defaults.md](contracts/schedules-and-model-defaults.md)
- Validation guide: [quickstart.md](quickstart.md)

## Complexity Tracking

No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
