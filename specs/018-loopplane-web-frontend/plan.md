# Implementation Plan: LoopPlane Web Frontend

**Branch**: `018-loopplane-web-frontend` (main-only) | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/018-loopplane-web-frontend/spec.md`

## Summary

A from-scratch single-page web UI under `apps/web/` (React + TypeScript + Vite, tested
with Vitest) over the unit-011 web/API host. It connects to the public `/v1` API —
`POST /v1/runs/events` (SSE) for a streamed run, the `/v1/sessions/*` endpoints for an
interactive session with approvals/questions, and the read-only `GET /v1/sessions`
inspection — carrying auth per the API boundary. The **testable core is pure
TypeScript** (an event-stream reducer, an SSE frame parser, and a fetch-based API
client), so the JS gate is deterministic and credential-free; the React components are
thin presentational wrappers over that core. The app changes **nothing** server-side
(it only consumes the existing API), embeds no secret, renders only metadata-safe
content, and its toolchain is isolated under `apps/` — the Python package, its build,
and its CI gates are untouched.

## Technical Context

**Language/Version**: TypeScript 5 (Node 20+; Node v24 + npm present in the environment)

**Primary Dependencies**: React 18, Vite 5 (build), Vitest 2 (test) — all under `apps/web/`,
isolated from the Python package; no Python dependency added

**Storage**: N/A (the browser app holds transient state; durability is server-side)

**Testing**: Vitest (node env for the pure core; jsdom for a few component smoke tests)
+ `tsc --noEmit` typecheck; the Python `pytest` suite stays unchanged

**Target Platform**: a modern browser; built to static assets

**Project Type**: web application (frontend under `apps/web/`, backend = unit 011)

**Performance Goals**: incremental render of the streamed run; responsive on long output

**Constraints**: consumes only the public `/v1` API; no secret in the bundle; no change
to the Python package or any prior contract; toolchain isolated under `apps/`

**Scale/Scope**: one new app (~10 source modules + tests) + a JS CI gate

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md`. | PASS |
| II — Greenfield | Written fresh from the spec; **no legacy/private UI copied** (FR-009). | PASS |
| III — Harness before automation | A presentation layer; adds no automation. | PASS |
| IV — Boundary Clarity | A separate app consuming only the public web API; one API-client seam. | PASS |
| V — Tool Gateway Ownership | The UI runs no tool — tools run server-side behind the API. | PASS |
| VI — Event Bus Ownership | The UI is a *consumer* of the normalized event stream over SSE; it renders, never re-emits. | PASS (FR-002/FR-003) |
| VII — Public-Safe | No secret in the bundle; metadata-only rendering; no legacy UI copy. | PASS (FR-006/FR-007/FR-009, SC-005) |
| VIII — No SDK Replacement | React is a UI library, not an agent runtime — not engaged. | PASS |
| IX — Reference, not clone | The UI is re-derived from the spec, not cloned. | PASS |
| X — Testable Evolution | Vitest tests + a build; rollback = remove `apps/web/`. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/018-loopplane-web-frontend/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── api-client.md            # the /v1 endpoints + SSE the UI consumes
│   └── integration-boundary.md  # UI ↔ web API; isolation from the Python package
└── tasks.md                     # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/web/                        # NEW frontend app (isolated JS toolchain)
├── package.json / vite.config.ts / tsconfig.json / index.html
├── src/
│   ├── main.tsx                 # mount the app
│   ├── App.tsx                  # shell: conversation + timeline + session list
│   ├── api/client.ts            # REST client over /v1 (auth header), pure + fetch-injectable
│   ├── api/events.ts            # parse SSE frames -> normalized event objects
│   ├── api/types.ts             # event/result types mirroring the API
│   ├── state/chat.ts            # reducer: events -> conversation + timeline state (pure)
│   ├── components/Conversation.tsx
│   ├── components/Timeline.tsx
│   ├── components/Prompts.tsx   # approval + question prompts
│   └── components/SessionList.tsx
└── src/__tests__/               # Vitest: reducer, event parsing, client (stubbed fetch), components

.github/workflows/web.yml        # the isolated JS CI gate (typecheck + vitest + build)
docs/web-frontend.md             # the guide
```

**Structure Decision**: A web application: the frontend lives under `apps/web/` with
its own `package.json`, build (Vite), and test runner (Vitest), entirely separate from
the Python package and its CI. The deterministic core (`api/events`, `api/client`,
`state/chat`) is pure TypeScript tested in Vitest's node env; the React components are
thin wrappers tested with a few jsdom smoke tests.

## Phases

- **Phase 0 — Research** (`research.md`): the `/v1` endpoints + SSE format the UI
  consumes (grounded in unit 011), the build/test toolchain choice, the pure-core
  testing strategy, auth carriage, and bundle public-safety.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the event/UI
  state model, the API-client contract, and the integration boundary.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — the pure core (events/reducer/client)
  tests first, then components, then the app shell + CI gate + docs.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
