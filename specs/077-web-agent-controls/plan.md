# Implementation Plan: Web Agent Controls

**Branch**: `main` | **Date**: 2026-07-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/077-web-agent-controls/spec.md`

## Summary

Add one host-owned, metadata-first Web Agent Controls category over existing plan mode, permission DSL/modes, cost/budget accounting, workspace context, upload/artifact references, and interaction transport. Permission selection is optional, host-approved, and applies to one accepted run only; the read projection supplies authoritative ephemeral active/last-accepted posture, and plan exit continues through the existing question/approval path. Existing cost/context/upload/artifact seams are reused, deterministic suggestions remain pure client presentation, and no durable browser policy state, Event Bus/checkpoint/Gateway/default/dependency change is introduced. The required additive control projection, per-run input field, and bounded non-image upload handoff are an explicit outward-contract/behavior human gate before implementation.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.6; React 18

**Primary Dependencies**: Existing AnyIO/Pydantic/FastAPI host and Web API; existing governance/approval/budget/context/upload/artifact boundaries; existing React/Vite Settings workspace. No new dependency or extra.

**Storage**: Existing checkpoint/session metadata, cost ledger, upload store, and artifact store only. Agent-control projection and per-run mode selection are ephemeral; no new table/file/record/migration or durable browser-managed setting.

**Testing**: pytest unit/contract/integration; Ruff; strict mypy; package build; TypeScript typecheck; Vitest; generated-type drift checks; Vite production build; Desktop compatibility tests; standalone Chromium accessibility/reflow matrix.

**Target Platform**: Browser SPA over the LoopPlane Web/API host; Desktop is compatibility-only through existing shared Web types/components.

**Project Type**: Full-stack additive feature across Python governance/host/Web API and the TypeScript Web Settings/chat surfaces.

**Performance Goals**: Every control category is reachable within two navigation actions and the unchanged conversation is restored in one action; deterministic suggestions add zero network/model/tool calls; control rendering introduces no document-level horizontal overflow at required viewports.

**Constraints**: Additive/default-preserving; selectable modes empty by default; `bypassPermissions` never browser-selectable; one accepted run only; no direct plan-exit toggle; deny-wins and approval ordering unchanged; no Event Bus/checkpoint schema/Gateway SPI or stage-order/dependency/default change; no raw rule expressions/config/paths/resource content; no new artifact/upload index or persistence; 076/080/081 spec/plan/tasks frozen; `.superpowers/**`, raw `openspec/**`, QA artifacts, and unknown user changes excluded; no stage/commit/push/release.

**Scale/Scope**: One new safe control projection, one optional run input field across existing submit transports, authoritative cost client integration, one Settings category, structured upload/reference convergence, deterministic suggestions, focused/full regression coverage, and delivery evidence for two principals and six viewport widths.

## Constitution Check

*GATE: Passed for planning before Phase 0 research and re-checked after Phase 1 design. The outward-contract gate recorded below was approved on 2026-07-27, so the authorized local implementation scope is unblocked.*

| Principle | Status | Notes |
|---|---|---|
| I. Spec-First Development | PASS | 077 spec, requirement checklists, research, plan, data model, contracts, quickstart, tasks, and analyze precede implementation. |
| II. Greenfield Implementation | PASS | Design is derived from current public-safe project code/contracts; no private reference or legacy implementation is copied. |
| III. Harness Before Loop Automation | PASS | The feature projects existing runtime behavior and adds no scheduler/automation layer. |
| IV. Runtime Boundary Clarity | PASS | Host/governance remain policy owners; WebAPI transports typed requests; Settings only projects/actions; no browser enforcement or durable transport-owned policy map. |
| V. Tool Gateway Ownership | PASS | Existing decide-stage policies remain the only tool authorization path; upload/artifact use after explicit send remains Gateway/authorized-handoff routed; no browser execution. |
| VI. Runtime Event Bus Ownership | PASS | Existing approval/question/tool/termination events are consumed unchanged; no event type/schema or re-emission. |
| VII. Public-Safe Documentation | PASS | Raw rules, config, credentials, paths, resource content, rejected values, local artifacts, and principal-private metadata are excluded. |
| VIII. No SDK Replacement | PASS | No runtime framework or SDK replacement. |
| IX. Reference, Not Clone | PASS | Existing LoopPlane units are reused on their own documented semantics. |
| X. Testable Evolution | PASS | Tasks are TDD-first by behavior slice and include focused/full validation, two-principal/browser evidence, per-slice rollback, and transaction-style completion. |

### Human/ADR gate record

**APPROVED — 2026-07-27**: The maintainer explicitly selected **「批准並實作（建議）」** for exactly these outward contract additions:

1. `GET /v1/sessions/{session_id}/agent-controls` with the safe owner-scoped response, including non-durable `active_run`/`last_accepted_run` authoritative posture, in `contracts/agent-control-projection.md`;
2. optional `permission_mode` on applicable run/session-turn/live-submit input, scoped to one accepted run;
3. the bounded non-image upload metadata handoff and `read_upload`-availability rejection semantics in `contracts/cost-context-and-references.md`; and
4. synchronized backend-owned generated Web type artifacts.

This approval authorizes local source, test, and generated-type implementation only. It does not authorize staging, commit, branch, push, pull request, tag, version, release, deployment, durable browser-mutated state, changed approval/enforcement ordering, Event Bus/checkpoint/Gateway/default/dependency changes, or a new artifact persistence/sharing boundary.

**No ADR is proposed at design time** because the selected design adds no durable browser-mutated state, persistence/event/checkpoint/Gateway/dependency/default change, approval/enforcement-order change, or new artifact sharing/storage boundary. If any of those becomes necessary, stop before implementation and produce an ADR plus a new maintainer gate.

## Project Structure

### Documentation (this feature)

```text
specs/077-web-agent-controls/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- checklists/
|   |-- requirements.md
|   `-- agent-controls-readiness.md
|-- contracts/
|   |-- agent-control-projection.md
|   |-- cost-context-and-references.md
|   |-- follow-up-suggestions.md
|   `-- delivery-convergence.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/loopplane/
|-- context.py                         # per-run requested posture metadata
|-- governance/
|   |-- modes.py                       # existing named-mode transforms/safe ids
|   `-- rule_dsl.py                    # reused deny-wins DSL; no rule editor
|-- budget/
|   `-- __init__.py                    # existing accounting + safe read posture
|-- controller/
|   `-- controller.py                  # single RunContext construction site
|-- host/
|   |-- agent_controls.py              # new safe DTO/provider/projection seam
|   |-- config.py                      # default-empty host-approved Web modes
|   |-- assembly.py                    # existing composition root/decider wiring
|   `-- host.py                        # per-run selection + projection facade
`-- webapi/
    |-- models.py                      # approved request/response models
    |-- app.py                         # owner-scoped route + submit forwarding
    |-- multimodal.py                  # backend-owned bounded upload-reference handoff
    `-- contract_types.py              # backend-owned shared type artifact source

apps/web/src/
|-- App.tsx
|-- api/
|   |-- client.ts
|   |-- types.ts
|   `-- generated.ts
|-- components/
|   |-- CapabilitySettingsView.tsx
|   |-- ChatHeader.tsx
|   |-- Composer.tsx
|   |-- Attachments.tsx
|   |-- MessageList.tsx
|   |-- ToolCard.tsx
|   `-- settings/
|       |-- SettingsLayout.tsx
|       `-- AgentControlsSettings.tsx  # new first-level Settings category
|-- state/
|   `-- chat.ts
|-- i18n/
|   `-- strings.ts
|-- styles.css
`-- __tests__/

apps/desktop/src/__tests__/

tests/
|-- unit/
|-- contract/
`-- integration/
```

**Structure Decision**: Keep policy selection inside the existing host/Gateway decide ownership: a default-empty host allow-list authorizes per-run mode identifiers, the single controller construction site stamps run metadata/plan state, and one context-reading decide policy selects existing named-mode/DSL behavior without adding a Gateway stage. Keep the outward projection in a narrow host module and expose it through one owner-scoped Web route. Add Agent Controls to the full-page Settings workspace introduced by 080; keep Inspection read-only, use Composer only for run-specific input, and reuse current session/context/reference state. Existing cost/context/upload/artifact routes remain unchanged.

## Phase 0: Research Output

See [research.md](research.md). Decisions:

- safe host projection plus optional per-run mode input and authoritative ephemeral active/last-accepted posture; no durable session/global mutation;
- default-empty mode allow-list and browser exclusion of `bypassPermissions`;
- context-reading mode/plan enforcement through existing deny-wins decide composition;
- existing exit-plan question/answer path with no direct Web exit;
- bounded permission summary rather than browser rule editing/evaluation;
- existing session/monthly cost reads plus safe guard posture, with unknown/unpriced never zero;
- existing context binding and structured upload submission, with an approved bounded backend non-image handoff only when `read_upload` is Gateway-advertised; current-session opaque artifact references only, with no raw-content browser fetch;
- pure deterministic suggestion function that only populates editable input;
- full-page Settings category, compact authoritative header cost, read-only Inspection;
- explicit outward-contract approval before implementation and no ADR unless design boundaries change.

## Phase 1: Design Output

- Data model: [data-model.md](data-model.md)
- Agent-control contract: [contracts/agent-control-projection.md](contracts/agent-control-projection.md)
- Cost/context/reference contract: [contracts/cost-context-and-references.md](contracts/cost-context-and-references.md)
- Suggestion contract: [contracts/follow-up-suggestions.md](contracts/follow-up-suggestions.md)
- Delivery contract: [contracts/delivery-convergence.md](contracts/delivery-convergence.md)
- Validation guide: [quickstart.md](quickstart.md)

## Post-Design Constitution Check

The pre-research statuses remain valid. Design artifacts explicitly preserve per-run/non-durable semantics, existing deny-wins/approval ordering, Tool Gateway/Event Bus/checkpoint ownership, current stores, dependencies, and defaults. They prohibit raw resource-content browser reads and cross-principal sharing. The additive outward Web/API contract was explicitly approved on 2026-07-27 for the scope recorded above; no unresolved architecture gate, complexity exception, or ADR remains for that authorized implementation.

## Complexity Tracking

No constitution violation is accepted. The outward-contract proposal is a required human gate, not a justified deviation.
