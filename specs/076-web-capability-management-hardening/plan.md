# Implementation Plan: Web Capability Management Hardening

**Branch**: `076-web-capability-management-hardening` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/076-web-capability-management-hardening/spec.md`

## Summary

Harden the 075 web capability-management surface from endpoint/form scaffolding into a product-usable, durable, owner-scoped settings experience. The feature adds durable per-principal capability state, shared read-only host capability visibility, principal-safe memory/skill/MCP runtime activation, real managed-MCP reconnect, an independent web settings view, catalog-only model defaults, a host-controlled mutation gate, public-safe errors, and rollback guidance.

The implementation approach is additive: keep existing 074 chat/session/live behavior and existing 075 read-only inspection and capability endpoints compatible, then layer a durable capability settings store and scoped runtime activation through existing host, web API, controller, and Tool Gateway seams. A narrow Tool Gateway extension is allowed only for owner-scoped managed adapters; it must stay inside the Tool Gateway boundary and be covered by boundary tests.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.6; React 18

**Primary Dependencies**: Existing FastAPI/AnyIO/Pydantic web host; existing LoopPlane host/controller/gateway/memory/skills/MCP/scheduler/model catalog/session seams; existing React/Vite web app. No required new runtime dependency is planned for 076.

**Storage**: Versioned per-principal JSON at `StorageConfig.root/capabilities/v1/<principal-hash>.json`, written with same-directory atomic replacement and process-local keyed locks; existing checkpoint/session state remains the owner of session metadata. Browser local/session state is used only for UI preferences. Browser-side provider credential and MCP token storage remain out of scope.

**Testing**: pytest for backend unit/integration/contract coverage; Vitest, TypeScript strict checks, and Vite build for web coverage; desktop TypeScript/Vitest gates for compatibility.

**Target Platform**: Browser SPA over the LoopPlane web/API host. Desktop remains compatibility-only through shared web state/components until the postponed desktop cowork parity unit.

**Project Type**: Full-stack web application increment over the existing Python runtime and TypeScript SPA.

**Performance Goals**: Capability settings lists load within 2 seconds in automated tests using representative owner/shared datasets; mutation flows settle into refreshed success or public-safe error state without page reload; owner-scoped tool descriptor filtering adds no visible delay to sending a turn in acceptance tests.

**Constraints**: Additive only; capability mutations and owner runtime activation default off; preserve 074 REST/SSE/live chat behavior; preserve 075 read-only inspection compatibility; preserve Tool Gateway ownership and its existing SPI/stage order; preserve Runtime Event Bus ownership and schemas; preserve checkpoint schemas; browser-managed MCP is policy-approved HTTP/SSE/WebSocket only and never stdio; schedule run-now uses a host-injected runner; preserve principal scoping; do not collect provider credentials or MCP auth tokens in the browser; do not modify raw `openspec/`; do not copy reference implementation code or private material.

**Scale/Scope**: One roadmap unit covering hardening for web capability management: memory, skills, MCP configuration, project/workspace context, schedules, model defaults, mutation gating, and settings UI. Web agent controls, plan/permission/budget controls, workspace files/artifact panels, follow-up suggestions, desktop cowork parity, and CLI/remote parity are deferred to later units.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --------- | ------ | ----- |
| I. Spec-First Development | PASS | Work is scoped by this spec, plan, generated contracts, and tasks. |
| II. Greenfield Implementation | PASS | No legacy/reference code is copied; private references remain out of scope. |
| IV. Runtime Boundary Clarity | PASS | Capability settings compose existing host/controller/gateway seams; scoped tool activation is explicitly owned by the Tool Gateway. |
| V. Tool Gateway Ownership | PASS | Managed skills/MCP tools remain resolved, authorized, and executed only through the Tool Gateway. |
| VI. Runtime Event Bus Ownership | PASS | No runtime event schema or frontend-specific loop event formatting changes are planned. |
| VII. Public-Safe Documentation | PASS | Artifacts avoid private paths, credentials, tokens, private hostnames, and raw reference material. |
| VIII. No SDK Replacement | PASS | No external agent framework replaces LoopPlane runtime ownership. |
| IX. Reference, Not Clone | PASS | Parity is expressed as behavior and mechanism, not copied implementation. |
| X. Testable Evolution | PASS | Contract, unit, integration, UI, compatibility, rollback, and public-safety validation are required. |

## Project Structure

### Documentation (this feature)

```text
specs/076-web-capability-management-hardening/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- capability-settings.md
|   |-- runtime-activation.md
|   `-- settings-ui.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/loopplane/
|-- host/
|   |-- capabilities.py
|   |-- capability_manager.py
|   |-- capability_store.py
|   `-- host.py
|-- gateway/
|   `-- gateway.py
|-- memory/
|-- skills/
|-- adapters/mcp/
|-- controller/
|-- loop/
`-- webapi/
    |-- app.py
    |-- models.py
    `-- contract_types.py

apps/web/src/
|-- api/
|   |-- client.ts
|   |-- generated.ts
|   `-- types.ts
|-- components/
|   |-- CapabilitySettings.tsx
|   |-- CapabilitySettingsView.tsx
|   |-- capabilities/
|   `-- InspectionPanel.tsx
`-- __tests__/

apps/desktop/src/
`-- __tests__/

tests/
|-- contract/
|-- integration/
`-- unit/
```

**Structure Decision**: 076 is a full-stack web hardening increment. Backend changes stay in existing host/webapi/controller/gateway/capability seams; frontend changes stay in the web app API/component layers; desktop source is touched only for compatibility tests or minimal shared-type compatibility. Runtime boundary-sensitive changes must be covered by focused boundary tests before UI work depends on them.

## Phase 0: Research Output

See [research.md](research.md). Key decisions:

- Store mutable capability settings as durable public-safe JSON under `StorageConfig.root`.
- Model ownership as user-owned mutable resources plus shared host read-only resources.
- Add a narrow scoped-adapter capability inside the Tool Gateway for managed skill/MCP runtime activation.
- Keep API changes additive and maintain existing 075 endpoint compatibility.
- Build an independent capability settings view while preserving the inspection panel as metadata-only.
- Use a host-controlled mutation gate for rollback and staged disablement.
- Keep mutations and owner runtime activation as independent explicit default-off host settings.
- Refuse browser-managed stdio and require a host-injected, default-deny endpoint policy for managed network MCP.
- Dispatch schedule run-now through a host-injected runner without importing the Phase-3 scheduler into host/webapi.

## Phase 1: Design Output

- Data model: [data-model.md](data-model.md)
- Capability settings contract: [contracts/capability-settings.md](contracts/capability-settings.md)
- Runtime activation contract: [contracts/runtime-activation.md](contracts/runtime-activation.md)
- Settings UI contract: [contracts/settings-ui.md](contracts/settings-ui.md)
- Validation guide: [quickstart.md](quickstart.md)

## Post-Design Constitution Check

| Principle | Status | Notes |
| --------- | ------ | ----- |
| I. Spec-First Development | PASS | Design artifacts and tasks will trace every implementation step to this unit. |
| II. Greenfield Implementation | PASS | Contracts describe new behavior without importing legacy/reference code. |
| IV. Runtime Boundary Clarity | PASS | Durable settings live in host-owned capability management; runtime use flows through declared controller/gateway seams. |
| V. Tool Gateway Ownership | PASS | Scoped managed adapters are added inside the Tool Gateway; no component bypasses tool resolution or execution. |
| VI. Runtime Event Bus Ownership | PASS | No event schema changes are introduced. |
| VII. Public-Safe Documentation | PASS | All artifacts use public-safe examples and fake host labels only. |
| VIII. No SDK Replacement | PASS | No agent framework substitution. |
| IX. Reference, Not Clone | PASS | Behavior is re-derived through LoopPlane specs. |
| X. Testable Evolution | PASS | Quickstart and tasks require focused tests plus compatibility gates. |

## Complexity Tracking

No constitution violations require complexity tracking for this feature.
