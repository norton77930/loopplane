# Implementation Plan: Web Capability Delivery Remediation

**Branch**: `main` | **Date**: 2026-07-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/081-web-capability-delivery-remediation/spec.md`

## Summary

Converge the uncommitted 076 capability hardening and 080 frontend presentation work before 077 by closing four verified-unit gaps under a new remediation unit: structurally reject unsafe browser-managed MCP endpoints at domain and persistence boundaries; await existing ToolGateway lease-safe retirement on update/delete/failure; add an optional principal-aware allowed-context provider; and replace scope-special-cased/edit-form details with action-driven safe read-only details. Preserve HTTP envelopes, Event Bus/checkpoint/Gateway contracts, dependencies, defaults, and frozen 076/080 history. Finish with fresh backend/Web/Desktop/Chromium/public-safety evidence and synchronized board/release/API documentation.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.6; React 18

**Primary Dependencies**: Existing AnyIO/Pydantic/FastAPI host and Web API; existing MCP adapter and ToolGateway; existing React/Vite Settings shell. No new dependency or extra.

**Storage**: Existing versioned per-principal capability JSON under `StorageConfig.root`; allowed contexts remain host-owned ephemeral projections and are never copied into the store.

**Testing**: pytest unit/contract/integration; Ruff; strict mypy; package build; TypeScript typecheck; Vitest; Vite production build; Chromium manual/accessibility matrix.

**Target Platform**: Browser SPA over the LoopPlane Web/API host; embedded Python host public methods; Desktop is compatibility-only through shared Web source/tests.

**Project Type**: Full-stack remediation across Python host/Web API and TypeScript Web UI.

**Performance Goals**: Capability list/detail operations remain within the existing 2-second acceptance target for representative owner/shared data; adapter removal is visible to new resolution before a mutation returns; no additional model or tool call is introduced by detail views.

**Constraints**: Additive remediation; no Event Bus/checkpoint schema/Gateway SPI or stage-order change; no dependency/default change; no new HTTP route or JSON envelope; public managed-MCP upsert/delete methods may become async per maintainer approval dated 2026-07-27; host endpoint policy stays default-deny; provider defaults to `None`; 076/080 spec/tasks frozen; `.superpowers/**`, raw `openspec/**`, and unknown user changes excluded; no commit/push/release without separate approval.

**Scale/Scope**: One remediation unit covering four security/contract gaps, one legacy UI removal, focused regression additions, full delivery gates, and documentation convergence. Unit 077 remains blocked until 081 Verified.

## Constitution Check

*GATE: Passed before Phase 0 research; re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Spec-First Development | PASS | 081 spec, research, plan, contracts, quickstart, checklist, and tasks precede implementation. |
| II. Greenfield Implementation | PASS | Fixes are derived from public-safe project artifacts and existing code; no legacy/reference code is copied. |
| IV. Runtime Boundary Clarity | PASS | Capability lifecycle remains host-owned; allowed contexts are host projections; session persistence remains controller-owned. |
| V. Tool Gateway Ownership | PASS | Manager only requests existing scoped-adapter replacement/removal; Gateway alone resolves, invokes, leases, retires, and shuts down tools. |
| VI. Runtime Event Bus Ownership | PASS | No event type, schema, emitter, transport, or consumer ownership change. |
| VII. Public-Safe Documentation | PASS | Endpoint values, credentials, private paths, local artifacts, and raw errors are excluded from committed projections/docs. |
| VIII. No SDK Replacement | PASS | No runtime framework or SDK replacement. |
| IX. Reference, Not Clone | PASS | Behavior is specified from LoopPlane requirements and existing boundaries. |
| X. Testable Evolution | PASS | Every tasks phase defines tests or requirement-quality validation, a completion checkpoint, and phase-specific rollback guidance; focused/full gates, browser acceptance, literal evidence, and working-tree ownership remain explicit. |

### Human approval record

The maintainer approved converting public Python managed-MCP upsert/delete host methods from sync to async on 2026-07-27 so they can await immediate Gateway retirement and lease-safe shutdown. HTTP routes and JSON responses remain unchanged. Any additional outward HTTP, default, dependency, schema, Gateway SPI/stage-order, Event Bus, or checkpoint change is a new stop-and-ask gate.

## Project Structure

### Documentation (this feature)

```text
specs/081-web-capability-delivery-remediation/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- checklists/
|   |-- requirements.md
|   `-- security-readiness.md
|-- contracts/
|   |-- managed-mcp-lifecycle.md
|   |-- allowed-context-and-shared-detail.md
|   `-- delivery-convergence.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/loopplane/
|-- host/
|   |-- capabilities.py
|   |-- capability_manager.py
|   |-- capability_store.py
|   |-- config.py
|   |-- assembly.py
|   `-- host.py
|-- gateway/
|   `-- gateway.py                 # reused, not redesigned
`-- webapi/
    |-- app.py
    |-- models.py
    `-- contract_types.py

apps/web/src/
|-- components/
|   |-- CapabilitySettingsView.tsx
|   `-- settings/
|       |-- CapabilityDetail.tsx
|       |-- MemorySettings.tsx
|       |-- SkillSettings.tsx
|       |-- McpSettings.tsx
|       `-- WorkspaceSettings.tsx
|-- api/
|-- i18n/
|-- styles.css
`-- __tests__/

apps/desktop/src/__tests__/

tests/
|-- unit/
|-- contract/
`-- integration/
```

**Structure Decision**: Keep all runtime fixes inside existing host capability seams and reuse Gateway lifecycle operations. Keep Web behavior in the six-module Settings architecture introduced by 080, with one shared read-only detail component. Existing routes and generated HTTP shapes remain stable; only approved public Python host method async semantics and the optional provider surface require API documentation updates.

## Phase 0: Research Output

See [research.md](research.md). Decisions:

- one structural endpoint validator shared by manager/reconnect/store;
- endpoint policy remains principal-aware and default-deny in manager;
- managed-MCP upsert/delete become async with approved host API change;
- existing Gateway retirement primitives are reused unchanged;
- optional provider returns principal-approved contexts; manager rebuilds safe projections and fails closed on collisions;
- existing HTTP detail shapes stay stable while shared owner-only fields are empty/not displayed;
- UI interactions are driven by projected actions through a reusable read-only detail component;
- 081 owns remediation evidence; 076/080 artifacts remain frozen.

## Phase 1: Design Output

- Data model: [data-model.md](data-model.md)
- MCP contract: [contracts/managed-mcp-lifecycle.md](contracts/managed-mcp-lifecycle.md)
- Context/detail contract: [contracts/allowed-context-and-shared-detail.md](contracts/allowed-context-and-shared-detail.md)
- Delivery contract: [contracts/delivery-convergence.md](contracts/delivery-convergence.md)
- Validation guide: [quickstart.md](quickstart.md)

## Post-Design Constitution Check

The pre-research PASS remains valid. The design introduces no package, dependency, schema, default, Gateway SPI/stage-order, Event Bus, checkpoint, or HTTP envelope change. The approved host API async conversion is recorded above; allowed contexts default to absent and preserve owner-only behavior. No complexity exception is required.

## Complexity Tracking

No constitution violations require complexity tracking.
