# Implementation Plan: LoopPlane Desktop GUI

**Branch**: `019-loopplane-desktop-gui` (main-only) | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/019-loopplane-desktop-gui/spec.md`

## Summary

A local Electron desktop app under `apps/desktop/` that runs the agent with **no
server**. An Electron main process spawns a **Python sidecar** (`sidecar/bridge.py`)
that drives `loopplane.host` and streams each normalized event over stdio as NDJSON
(the serverless equivalent of the unit-011 SSE host, reusing `serialize_event`). The
renderer **reuses the unit-018 UI** (the same `reduce` + components) wired to a
**sidecar transport** (`window.api` IPC) instead of HTTP. The substantive, testable
parts are the **Python bridge** (covered in the Python gate) and the **TS transport**
(covered in the JS gate); the Electron shell's launch wiring is typechecked and
verified by a manual smoke (Electron's binary is skipped in CI). Packaging a signed,
distributable installer is **out of scope** (reserved). The app composes 011/012/018
and the host, changing nothing in them, runs no tool itself, and embeds no secret.

## Technical Context

**Language/Version**: TypeScript 5 (Electron 32, Node 20+) + Python 3.12 (the sidecar)

**Primary Dependencies**: electron, typescript, vitest (under `apps/desktop/`,
`ELECTRON_SKIP_BINARY_DOWNLOAD=1` in CI); the sidecar uses only `loopplane` (no new dep)

**Storage**: N/A (the host's configured stores apply server-side as before)

**Testing**: the Python bridge in the `pytest` gate (loaded by path from
`apps/desktop/sidecar`); the TS transport in Vitest; `tsc --noEmit` for the shell

**Target Platform**: a desktop (Windows/macOS/Linux via Electron)

**Project Type**: desktop application (Electron shell + Python sidecar + reused 018 UI)

**Performance Goals**: local, in-process latency bound by the model

**Constraints**: serverless (no port); reuses 018 (no second UI, no legacy copy); no
secret; isolated under `apps/`; changes nothing in 011/012/018 or the runtime

**Scale/Scope**: one new app (Electron main/preload + a thin renderer + a Python
sidecar bridge) + tests; no installer

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md`. | PASS |
| II — Greenfield | The shell is written fresh; the UI is **reused** from 018, not copied from any legacy (VII). | PASS |
| III — Harness before automation | A presentation shell; adds no automation. | PASS |
| IV — Boundary Clarity | Composes the public host + the 018 UI; the bridge is one declared transport. | PASS |
| V — Tool Gateway Ownership | The renderer runs no tool — tools run in the host behind the gateway. | PASS (FR-006) |
| VI — Event Bus Ownership | The bridge is a streaming **consumer** of the normalized stream (reuses `serialize_event`); it re-emits nothing. | PASS (FR-002) |
| VII — Public-Safe | No secret in the app; reuses 018 (no legacy UI copy); metadata-only rendering. | PASS (FR-003/FR-007, SC-004) |
| VIII — No SDK Replacement | Electron is a shell; the runtime is unchanged. | PASS |
| IX — Reference, not clone | The shell is re-derived; the UI is reused, not cloned. | PASS |
| X — Testable Evolution | Python bridge + TS transport tests + a typechecked shell; rollback = remove `apps/desktop/`. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/019-loopplane-desktop-gui/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── bridge.md                # the stdio NDJSON protocol + the Python sidecar
│   └── integration-boundary.md  # composes host + 018; isolation; reserved packaging
└── tasks.md                     # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/desktop/                    # NEW desktop app (isolated toolchain)
├── package.json / tsconfig.json
├── electron/
│   ├── main.ts                  # spawn the sidecar; create the window; bridge stdio <-> IPC
│   └── preload.ts               # expose window.api (send/onEvent) to the renderer
├── src/
│   ├── sidecar.ts               # TS transport: window.api -> RawEvent stream (mirrors 018's client)
│   ├── App.tsx                  # reuses 018's reduce + components over the sidecar transport
│   ├── main.tsx                 # mount
│   └── __tests__/sidecar.test.ts  # Vitest: the transport over a stubbed window.api
└── sidecar/
    └── bridge.py                # stdio NDJSON bridge over loopplane.host (reuses serialize_event)

tests/integration/test_desktop_sidecar.py   # Python gate: load bridge.py by path, assert event frames
docs/desktop-gui.md                          # the guide
```

**Structure Decision**: A desktop app under `apps/desktop/`. The Python sidecar
(`sidecar/bridge.py`) reuses `loopplane.host` + `serialize_event` and is tested in the
existing `pytest` gate (loaded by file path, so it is not added to the wheel). The TS
transport reuses 018's `RawEvent`/`reduce` via a `@web` path alias and is tested in
Vitest. The Electron main/preload glue is typechecked; the GUI smoke is manual
(`ELECTRON_SKIP_BINARY_DOWNLOAD=1` keeps CI binary-free), and packaging is reserved.

## Phases

- **Phase 0 — Research** (`research.md`): the 012 sidecar contract, the `serialize_event`
  seam (reused from the webapi), the stdio NDJSON protocol, reusing 018 via a path
  alias, and the testing split (Python bridge / TS transport / manual Electron smoke).
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the bridge
  protocol, the transport, and the integration boundary.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — the Python bridge test + impl, the TS
  transport test + impl, then the Electron shell (typechecked) + docs.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
