# Phase 0 Research: Web Frontend

Grounded in the unit-011 web/API host; the UI is written fresh from the spec.

## R1 — The `/v1` API the UI consumes

From `loopplane.webapi` (auth boundary on every route, `/v1` prefix):

| Need | Endpoint |
|---|---|
| streamed one-shot run | `POST /v1/runs/events` `{prompt}` → SSE `text/event-stream` |
| one-shot outcome | `POST /v1/runs` `{prompt}` → `RunResult` |
| open interactive session | `POST /v1/sessions` → `{session_id}` |
| session event stream | `GET /v1/sessions/{id}/events` → SSE |
| submit to a session | `POST /v1/sessions/{id}/submit` `{prompt}` → `RunResult` |
| answer approval | `POST /v1/sessions/{id}/approvals/{request_id}` `{allow,scope,reason}` |
| answer question | `POST /v1/sessions/{id}/questions/{request_id}` `{answers}` |
| cancel | `POST /v1/sessions/{id}/cancel` |
| list sessions | `GET /v1/sessions` → `SessionSummaryView[]` |
| session history | `GET /v1/sessions/{id}/history` |
| resume | `POST /v1/sessions/{id}/resume` |

**Decision**: the UI's `api/client.ts` wraps exactly these endpoints and is
**fetch-injectable** (a `fetch` function is a constructor param), so tests stub the
network with no server. The UI changes nothing server-side (FR-001/FR-010).

## R2 — The SSE event stream

The SSE stream forwards each normalized event serialized verbatim (one event per SSE
`data:` frame, JSON). **Decision**: `api/events.ts` parses an SSE byte stream into a
sequence of event objects (split on the SSE frame boundary, `JSON.parse` each `data:`
line), typed by the event `type` discriminator (`assistant-output-increment`,
`tool-call-started`, `tool-call-completed`, `run-terminated`, `approval-requested`,
`question-asked`, …). The parser is pure and unit-tested against canned frames.

## R3 — UI state: an event reducer

**Decision**: `state/chat.ts` is a pure reducer `(state, event) -> state` that folds
the event stream into the view model: the conversation (user prompts + accumulating
assistant text per turn), the timeline (ordered metadata-only entries: turn, tool
name+outcome, termination), and any pending approval/question. Pure reducer = the
bulk of coverage is deterministic Vitest with no DOM. React components select from
this state.

## R4 — Toolchain (isolated under `apps/`)

**Decision**: React 18 + TypeScript + Vite (build) + Vitest (test). Everything lives
under `apps/web/` with its own `package.json`; the Python package, `pyproject.toml`,
and the Python CI gates are untouched (FR-010). A separate `.github/workflows/web.yml`
runs `tsc --noEmit`, `vitest run`, and `vite build`. The wheel excludes `apps/` (the
hatch build targets only `src/loopplane`), so packaging is unchanged.

## R5 — Testing strategy (deterministic, credential-free)

**Decision**: the pure core (`api/events`, `state/chat`, `api/client` with a stubbed
`fetch`) is tested in Vitest's node env; a few component smoke tests use jsdom +
Testing Library to confirm a streamed run renders and a prompt submits. No real
network, no credentials — SC-006's "component tests pass" is met by the JS gate.

## R6 — Public-safety (FR-006/FR-007, SC-005)

**Decision**: the client carries auth via a header the embedder supplies at runtime
(never baked into the bundle); the UI renders only the metadata-safe fields the API
already exposes (assistant text; tool name + outcome; normalized termination;
public-safe session id + recency). A bundle scan in the JS gate asserts no secret.
Error/disconnect states are explicit (FR-008).
