# Implementation Plan: Desktop Capability Parity

**Branch**: `083-desktop-capability-parity` | **Spec**: [spec.md](./spec.md)
**Depends on**: 078 Verified; 075/076/077 (Web capability management and agent controls); 064 (cost surfacing); 065 (host commands)

## Summary

Project capability management and cost onto Desktop through the existing sidecar protocol, and extract the Web settings panels into the shared presentation package so both surfaces render one implementation.

The decisive finding from design research: **there is no runtime work in this unit.** Every capability it needs is already a public method on `LoopPlaneHost`, and the sidecar already holds a Host and is already permitted to import `loopplane.host`. Web reaches these methods through unit-011 HTTP endpoints; Desktop will reach the same methods through sidecar RPC. Nothing below the host moves.

## Technical Context

**Language / stack**: Python 3.12 sidecar (`apps/desktop/sidecar`), TypeScript/React renderer and Electron main (`apps/desktop`), shared presentation (`packages/cowork-presentation`).

**Existing host surface this unit projects** (verified in `src/loopplane/host/host.py`):

| Domain | Host methods |
| --- | --- |
| Memory | `list_managed_memory`, `write_managed_memory`, `get_managed_memory`, `delete_managed_memory` |
| Skills | `list_managed_skills`, `write_managed_skill`, `import_managed_skill`, `get_managed_skill`, `delete_managed_skill` |
| MCP | `list_managed_mcp`, `get_managed_mcp`, `upsert_managed_mcp`, `delete_managed_mcp` |
| Workspace contexts | `list_workspace_contexts`, `upsert_workspace_context`, `get_workspace_context`, `delete_workspace_context` |
| Schedules | `list_managed_schedules`, `upsert_managed_schedule`, `get_managed_schedule`, `delete_managed_schedule` |
| Model default | `model_default`, `set_model_default` |
| Cost | `session_cost`, `monthly_spend` |

**Presentation reuse**: `packages/cowork-presentation/src/components/settings/AgentControlsSettings.tsx` already accepts a narrow `service` interface rather than a transport, and is rendered by both apps. The six remaining panels in `apps/web/src/components/settings/` each take `ApiClient` as a type dependency and must be given the same treatment before Desktop can render them.

**Scale**: one local profile, one interactive lease, tens of managed records per domain. No pagination requirement beyond what the host already returns.

**Constraints inherited from 078**:
- `tests/contract/test_desktop_boundary.py` admits `loopplane.{host,events,errors,model,adapters}` only, forbids store/controller/gateway/tool imports, and forbids `.invoke(` and direct SQLite.
- `tests/integration/test_desktop_sidecar.py` pins the complete method list by **exact equality**.
- `dispatcher.py` rejects an initialize request naming a capability outside `REQUESTED_CAPABILITIES`; that enumeration is not extended here.
- `scripts/smoke-desktop-artifact.ps1` requires seven fixed Name/ControlType pairs, each exactly once, the literal word `usable` in the runtime-status group, and the success marker inside the pane body's accessibility subtree. See `docs/desktop-gui.md`.

## Constitution Check

| Principle | How this unit satisfies it |
| --- | --- |
| **I — Spec-first** | This spec/plan/tasks tree is the artifact. No ADR is required: no boundary is blurred and no new architectural decision is taken. |
| **III — Normalized events** | No event type, payload, reason, or schema version changes. Capability management is host state, not run state. |
| **IV — Component boundaries** | Electron main keeps process/IPC ownership, the sidecar keeps profile/adaptation, the Host keeps policy. New methods are projections, not reach-through. |
| **V — Gateway-only execution** | Nothing here executes a tool. `/compact`, `/cost`, `/model`, `/memory` are host UX over `CommandRegistry`, as 065 established. |
| **VII — Public-safe diagnostics** | Every projection is metadata-only; MCP endpoints and credentials never leave main-adjacent code. Failures map to the fixed public catalogue. |
| **VIII — Boundary definition** | No boundary changes, so no ADR update. If implementation finds one, stop and raise it before proceeding. |
| **X — Default-preserving, reversible** | Every domain reports unavailable when the host has not configured it; nothing is forced on. Reverting the commits restores current behavior. |

## Project Structure

### Documentation (this feature)

```
specs/083-desktop-capability-parity/
├── spec.md
├── plan.md
└── tasks.md
```

### Source

```
apps/desktop/sidecar/methods/
├── capability.py          # NEW: memory / skills / MCP projections + mutations
├── governance.py          # NEW: schedules / contexts / model default
└── cost.py                # NEW: session + monthly spend projections

apps/desktop/sidecar/bridge.py          # register methods; extend _DESKTOP_METHOD_NAMES
apps/desktop/electron/ipc-channels.ts   # new lp:capability:* / lp:governance:* / lp:cost:* channels
apps/desktop/electron/ipc-handlers.ts   # handlers with guard() + main-generated mutation ids
apps/desktop/electron/preload.ts        # typed facade groups
apps/desktop/src/global.d.ts            # renderer types

packages/cowork-presentation/src/components/settings/
├── McpSettings.tsx        # MOVED from apps/web, behind a service port
├── MemorySettings.tsx     # MOVED
├── SkillSettings.tsx      # MOVED
├── ScheduleSettings.tsx   # MOVED
├── WorkspaceSettings.tsx  # MOVED
└── ModelDefaultSettings.tsx # MOVED

apps/web/src/components/settings/*.tsx  # become thin adapters over ApiClient
apps/desktop/src/services/*.ts          # NEW: sidecar-backed service adapters
apps/desktop/src/App.tsx                # settings tabs; cost in the context strip
apps/desktop/src/i18n.tsx               # en + zh-TW for every added string

tests/unit/test_desktop_capability_methods.py    # NEW
tests/unit/test_desktop_governance_methods.py    # NEW
tests/integration/test_desktop_sidecar.py        # exact method list updated
tests/contract/test_desktop_public_safety_routing.py  # new projections covered
```

## Implementation Strategy

Each wave is an independent revert boundary and ends green on all gates.

### Wave 1 — Cost visibility (US1)

`cost.py` projecting `session_cost` / `monthly_spend` as exact `Decimal` strings or explicit absence; one IPC channel group; the session figure joins the header context strip and the detail joins Inspection. The distinction between unpriced, partially priced, unavailable, and zero is carried in the projection, never reconstructed in the renderer.

### Wave 2 — Model selection (US2)

Extend the provider settings from ADR 0016 with a catalog read and a per-session selection. Selection is a renderer-held choice submitted with the run, matching how Web routes a model, rather than a new durable field. Refused while a run is in flight.

### Wave 3 — Presentation extraction (FR-020)

Move the six panels into the shared package behind service ports, following `AgentControlsSettings`. **No new behavior in this wave**, so Web's contract suites are the proof it landed correctly. Do this before Wave 4 so the later waves wire an already-shared component instead of writing a second one.

### Wave 4 — Capability management (US3)

`capability.py` for MCP, skills, and memory, with mutations behind the profile mutation lease. Desktop service adapters; settings tabs. MCP is first because its safety surface is the largest.

### Wave 5 — Governance surface (US4)

`governance.py` for schedules, workspace contexts, and the model default.

### Wave 6 — Host commands (US5)

Wire `CommandRegistry` into the composer, mirroring the CLI and Web paths. No Gateway, no Event Bus.

### Wave 7 — Docs, evidence, board

`docs/desktop-gui.md` gains a capability-management section; `docs/capabilities.md` gains the 083 row; the board transitions only on maintainer approval.

## Verification Matrix

| Claim | Evidence |
| --- | --- |
| No runtime change | `git diff --stat src/loopplane` is empty for the unit |
| Protocol contract intact | `tests/integration/test_desktop_sidecar.py` exact list updated deliberately; protocol version and `REQUESTED_CAPABILITIES` unchanged |
| Boundary intact | `tests/contract/test_desktop_boundary.py` green with a negative self-check |
| No credential or endpoint leak | `tests/contract/test_desktop_public_safety_routing.py` extended per projection; repository public-safety scan clean |
| Untrusted senders rejected | one test per new IPC channel |
| Web unchanged | `tests/contract/test_web_*_contract.py`, `test_webapi_boundary.py`, `test_web_type_artifacts.py`, and the Web Vitest suite green without edits |
| Packaged app still drivable | `scripts/smoke-desktop-artifact.ps1 -Scenario all` green under the delivery job |
| Bilingual | the i18n coverage test |

## Rollback and Default Preservation

- Every domain defaults to unavailable when the host has not configured it; no host configuration is implied or created.
- Removing this unit's sidecar methods, IPC channels, preload groups, and settings tabs restores 078 behavior exactly.
- The presentation extraction is separately revertible: restoring the six panels to `apps/web` leaves Web as it is today.
- No checkpoint, event, reason, schema, default, or dependency changes, so no migration exists to undo.

## Complexity and Risk

| Risk | Handling |
| --- | --- |
| The exact-equality method list is easy to forget | It is a named task in every wave that adds a method, not a cleanup step |
| MCP configuration carries endpoints and credentials | Projections are allow-listed field by field; a routing test asserts absence rather than presence |
| Extraction could move Web behavior | Wave 3 adds no behavior, so any Web contract failure is a genuine regression rather than an expected diff |
| Renderer-held model selection could drift from host acceptance | The host remains authoritative; the renderer shows the accepted selection, never its own draft, as 077 established |
| Growth of the settings surface could crowd the sidebar footer | Settings remains one entry opening a tabbed view; no new top-level navigation |

## Not Decided Here

A native application menu, keyboard shortcuts, and window-title state require `apps/desktop/electron/main.ts` and are deliberately excluded (NG-003). If Desktop later needs attachments for a reason other than parity, that is a separate decision with its own threat model, not a gap in this unit.
