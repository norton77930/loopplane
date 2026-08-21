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
| MCP | `list_managed_mcp`, `get_managed_mcp`, `upsert_managed_mcp`, `reconnect_managed_mcp`, `delete_managed_mcp` |
| Workspace contexts | `list_workspace_contexts`, `upsert_workspace_context`, `get_workspace_context`, `delete_workspace_context`, `bind_session_context` |
| Schedules | `list_managed_schedules`, `upsert_managed_schedule`, `get_managed_schedule`, `enable_managed_schedule`, `disable_managed_schedule`, `run_managed_schedule_now`, `delete_managed_schedule` |
| Model default | `model_default`, `set_model_default`, `clear_model_default` |
| Cost | `session_cost`, `monthly_spend` (both `Decimal \| None`); the pricing-completeness distinction lives on `agent_controls(session_id).budget.pricing` (`priced` / `partially_unpriced` / `unpriced` / `unknown`) |

The service surface of each moved Web panel defines which of these the sidecar must project — the Web schedule panel, for example, already offers list / upsert / get / run-now / enable / disable / delete.

**Presentation reuse**: `packages/cowork-presentation/src/components/settings/AgentControlsSettings.tsx` already accepts a narrow `service` interface rather than a transport, and is rendered by both apps. The six remaining panels in `apps/web/src/components/settings/` each take `ApiClient` as a type dependency and must be given the same treatment before Desktop can render them.

**Scale**: one local profile, one interactive lease, tens of managed records per domain. No pagination requirement beyond what the host already returns.

**Constraints inherited from 078**:
- `tests/contract/test_desktop_boundary.py` admits `loopplane.{host,events,errors,model,adapters}` only, forbids store/controller/gateway/tool imports, and forbids `.invoke(` and direct SQLite.
- `tests/integration/test_desktop_sidecar.py` pins the complete method list by **exact equality in two places** — the packaged-handshake assertion and the in-process dispatcher assertion.
- `apps/desktop/electron/sidecar-rpc.ts` validates the handshake's announced methods by **exact membership** against `REQUIRED_METHODS`; a new sidecar method missing there makes the client refuse the runtime as incompatible.
- `dispatcher.py` rejects an initialize request naming a capability outside `REQUESTED_CAPABILITIES`; that enumeration is not extended here.
- `scripts/smoke-desktop-artifact.ps1` requires seven fixed Name/ControlType pairs, each exactly once, the literal word `usable` in the runtime-status group, and the success marker inside the pane body's accessibility subtree. See `docs/desktop-gui.md`.

## Constitution Check

| Principle | How this unit satisfies it |
| --- | --- |
| **I — Spec-first** | This spec/plan/tasks tree is the artifact, plus one ADR: **0017** admits `loopplane.commands` to the sidecar import allow-list (the Wave 6 boundary decision). No other architectural decision is taken. |
| **III — Normalized events** | No event type, payload, reason, or schema version changes. Capability management is host state, not run state. |
| **IV — Component boundaries** | Electron main keeps process/IPC ownership, the sidecar keeps profile/adaptation, the Host keeps policy. New methods are projections, not reach-through. |
| **V — Gateway-only execution** | Nothing here executes a tool. `/compact`, `/cost`, `/model`, `/memory` are host UX over `CommandRegistry`, as 065 established. |
| **VII — Public-safe diagnostics** | Every projection is metadata-only; MCP endpoints and credentials never leave main-adjacent code. Failures map to the fixed public catalogue. |
| **VIII — Boundary definition** | One boundary-definition update — the sidecar import allow-list gains `loopplane.commands` — was raised at the Wave 6 gate, decided by the maintainer (2026-08-19), and recorded as **ADR 0017**. No other boundary moves. |
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

`cost.py` projecting `session_cost` / `monthly_spend` as exact `Decimal` strings or explicit absence; one IPC channel group; the session figure joins the conversation pane's status area and the detail joins Inspection. The distinction between unpriced, partially priced, unavailable, and zero is carried in the projection, never reconstructed in the renderer — its source is the `budget.pricing` literal on the host's agent-controls projection (`LoopPlaneHost.agent_controls`), because `session_cost` alone is a bare `Decimal | None` and cannot express it. The cost domain also gains its availability card in the `capabilities.list` projection (FR-012).

### Wave 2 — Model selection (US2)

**Maintainer decision (2026-08-19): re-scoped to option (a) below.** The wave delivers a one-step, catalog-driven switch over the existing ADR 0016 provider path, entirely in Electron main and the renderer — no sidecar method, no registry change, no runtime change:

- A curated per-provider model catalog lives as static data in `apps/desktop/electron/provider-catalog.ts` and is answered over a new guarded `lp:providers:catalog` channel that reads the vault's current provider + model id (the vault, not the spawn env, is the truth after a save).
- The provider settings panel offers the catalog on the model field (free-form input stays possible) and gains a one-step "save and restart" action: the existing `providersSave` (model id only — the stored key is reused) followed by the existing `providersRestart`. Disabled while a run is in flight.
- True per-session switching is deferred to a future runtime unit: `ModelRequest.model: str | None = None` (additive), adapters honoring the override, the loop feeding `session.model` — same-provider switching without relaunch, also benefiting single-host Web deployments.

The original verification gate and its outcome are kept below for the record.

Before any Wave 2 code: verify the interactive-session path can carry a per-run model without touching `src/loopplane` — `LoopPlaneHost.run` accepts `model=`, but the interactive `submit()` the Desktop sidecar drives does not. If no sidecar-side route exists (for example re-creating the interactive session with the selection applied), the no-runtime-work premise has failed for this wave: stop and re-plan it before writing code.

**Verified 2026-08-15: the premise FAILED and this wave is stopped pending a maintainer decision.** The `model` parameter reaches `controller.create_session`, but on Desktop's single host the string is metadata only — `ModelBoundary.stream_turn(ModelRequest)` carries no model id, so the adapter always answers with its construction-time model; Web's selector works by routing to a per-model host, which one-profile Desktop cannot mirror. Options: (a) re-scope US2 to catalog-driven selection over the existing provider-settings path (`providersSave` model-id change reuses the stored key + `providersRestart`) — honest, no runtime change, but a relaunch remains; (b) authorize an additive runtime change (`ModelRequest.model: str | None = None`, adapters honor it, the loop feeds `session.model`) as its own unit — true same-provider per-session switching, but a model-boundary contract change outside this unit's no-runtime-work premise; (c) defer the wave. Waves 3–5 are independent of this decision.

### Wave 3 — Presentation extraction (FR-020)

Move the six panels into the shared package behind service ports, following `AgentControlsSettings`. **No new behavior in this wave**, so Web's contract suites are the proof it landed correctly. Do this before Wave 4 so the later waves wire an already-shared component instead of writing a second one.

### Wave 4 — Capability management (US3)

`capability.py` for MCP, skills, and memory, with mutations behind the profile mutation lease. Desktop service adapters; settings tabs. MCP is first because its safety surface is the largest.

### Wave 5 — Governance surface (US4)

`governance.py` for schedules, workspace contexts, and the model default.

### Wave 6 — Host commands (US5)

Wire `CommandRegistry` into the composer, mirroring the CLI and Web paths. No Gateway, no Event Bus.

The sidecar has no command surface today, and `CommandRegistry` lives in `loopplane.commands` — a module the sidecar boundary contract (`tests/contract/test_desktop_boundary.py`) does not admit. Wave 6 therefore opened with a boundary decision gate.

**Maintainer decision (2026-08-19): admitted, recorded as ADR 0017.** `loopplane.commands` joins the sidecar import allow-list — the sidecar is the registry's third host-UX consumer beside `cli/session.py` and `webapi/app.py`, and commands are host UX, not tools, so Gateway-only execution (Constitution V) is untouched. The wave adds a `command.execute` sidecar method with the full FR-015 registry discipline, one guarded IPC channel with its untrusted-sender test, and composer interception of a leading `/` rendered as a local user/assistant entry pair with no run, no Gateway, and no Event Bus.

### Wave 7 — Docs, evidence, board

`docs/desktop-gui.md` gains a capability-management section; `docs/capabilities.md` gains the 083 row; the board transitions only on maintainer approval.

## Verification Matrix

| Claim | Evidence |
| --- | --- |
| No runtime change | `git diff --stat src/loopplane` is empty for the unit |
| Protocol contract intact | both exact lists in `tests/integration/test_desktop_sidecar.py` and `REQUIRED_METHODS` in `sidecar-rpc.ts` updated deliberately; protocol version and `REQUESTED_CAPABILITIES` unchanged |
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
| The method registries are easy to forget (bridge list, two test lists, TS `REQUIRED_METHODS`) | Updating all of them is a named task in every wave that adds a method, not a cleanup step |
| MCP configuration carries endpoints and credentials | Projections are allow-listed field by field; a routing test asserts absence rather than presence |
| Extraction could move Web behavior | Wave 3 adds no behavior, so any Web contract failure is a genuine regression rather than an expected diff |
| Renderer-held model selection could drift from host acceptance | The host remains authoritative; the renderer shows the accepted selection, never its own draft, as 077 established |
| Growth of the settings surface could crowd the sidebar footer | Settings remains one entry opening a tabbed view; no new top-level navigation |

## Not Decided Here

A native application menu, keyboard shortcuts, and window-title state require `apps/desktop/electron/main.ts` and are deliberately excluded (NG-003). If Desktop later needs attachments for a reason other than parity, that is a separate decision with its own threat model, not a gap in this unit.
