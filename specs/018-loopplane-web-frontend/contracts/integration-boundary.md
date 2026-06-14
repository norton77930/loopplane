# Contract: Frontend Integration Boundary

How the web UI relates to the rest of the repository **without changing anything
server-side or in the Python package**.

## UI ↔ web API (unit 011)

- The UI talks **only** to the public `/v1` API over HTTP/SSE; it never imports or
  reaches the runtime, and it never executes a tool (Constitution V) — tools run
  server-side behind the gateway.
- The UI is a **consumer** of the normalized event stream (Constitution VI): it parses
  SSE frames and renders them; it re-emits nothing.
- The web API contract (unit 011) is **unchanged** — no endpoint is added, modified, or
  removed by this unit.

## Isolation from the Python package

- The frontend lives under `apps/web/` with its own `package.json`, build, and test
  runner. The Python package, `pyproject.toml`, the wheel contents (`src/loopplane` +
  `py.typed`), and the Python CI gates are **untouched** (FR-010, SC-006).
- The hatch wheel target is `src/loopplane`, so `apps/` is excluded from the
  distribution; the unit-014 packaging / api-reference / docs-index contracts are
  unaffected (the api-reference covers Python packages only; `docs/web-frontend.md` is
  added to the docs index).
- A separate JS CI gate (`.github/workflows/web.yml`) runs the typecheck, Vitest, and
  the build — it does not touch the Python gate.

## Public-safety

- No secret or credential is embedded in the client source or the built bundle (VII);
  auth is supplied at runtime.
- The UI renders only metadata-safe content; raw tool I/O, secrets, private paths, and
  raw exceptions never appear.
