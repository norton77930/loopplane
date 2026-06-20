# Tasks: Per-Principal Host Pool

**Feature**: 061-tenant-host-pool | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0009](../../docs/adr/0009-tenant-host-pool.md)

**Scope**: additive — a per-principal `TenantHostPool` above the web/API host (pool-above-host, the
maintainer fork). create_app gains an optional pool param; default (no pool) = the existing single
shared host (byte-identical). host/loop/gateway/event UNCHANGED. Confined to loopplane.webapi.

**Tests**: requested (offline/in-process).

## Phase 1: The pool (P1) 🎯

- [ ] T001 Create `src/loopplane/webapi/pool.py` `TenantHostPool`: holds a host FACTORY
  (`Callable[..., LoopPlaneHost]`), a per-principal in-flight cap, and an optional max-principals
  bound. `host_for(principal_id, model=None) -> LoopPlaneHost` lazily builds + caches a per-principal
  host (reused across that principal's requests) and bounds per-principal in-flight runs (an
  `anyio.Semaphore`/counter); exceeding a cap is rejected/bounded; one principal's host failure is
  isolated (per-principal entry). Principal ids are opaque (never logged with secrets). Each
  principal's host keeps its own sequential `_active` invariant (the pool does NOT touch the host).

## Phase 2: create_app wiring (P1)

- [ ] T002 In `src/loopplane/webapi/app.py`: add an OPTIONAL `host_pool: TenantHostPool | None = None`
  param to `create_app`. When None (default): the existing single shared `host` + `_select(model)`
  path is used VERBATIM (byte-identical — one shared host; the existing 409 on a concurrent run).
  When set: the per-principal session/run routes resolve the host via
  `host_pool.host_for(principal.id, model)` (wrapping/replacing the shared `_select` for those
  routes). Keep the change minimal + behind the None default.

## Phase 3: Export + docs (P1)

- [ ] T003 Export `TenantHostPool` from `src/loopplane/webapi/__init__.py` (additive `__all__`) and
  add it to `docs/api-reference.md` under `loopplane.webapi` (so the api-reference bijection stays
  exact).

## Phase 4: Tests (P1/P2) — offline/in-process

- [ ] T004 Add webapi pool tests (offline/in-process, mirroring the existing webapi/host test
  harness): (a) concurrent principals — with a pool + a host factory, principal A and principal B run
  concurrently (neither raises "a run is already active"); (b) same-principal sequential — A's second
  concurrent run is rejected (the per-host `_active` invariant holds); (c) default-off byte-identity —
  no pool → single shared host; behavior byte-identical (the existing 409 on a concurrent run; the
  existing webapi tests pass); (d) bounded — a per-principal in-flight cap exceeded → rejected/bounded;
  (e) contained — one principal's host failure isolated; (f) a principal id is never echoed with a
  secret.

## Phase 5: Gates

- [ ] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm the structural audits
  (`test_no_execution_path_outside_the_gateway` [controller/loop must not import the tools layer],
  `test_public_safety`) + the api-reference-bijection test (the new `TenantHostPool` documented) + the
  existing webapi/host suite pass unchanged. SCHEMA_VERSION unchanged (no event change). NOTE: do not
  run the full pytest concurrently with the verify Workflow (the real-subprocess MCP tests flake under
  CPU load — re-run any such failure in isolation with a fresh --basetemp).

## Dependencies

- T001 → T002 → T003 → T004 → T005 (gates last).

## Implementation strategy

- Confined to `loopplane.webapi` (the pool + the create_app wiring + tests). May be done inline or via
  a fork; then the four gates + the structural audits + the api-reference bijection + an adversarial
  verify (default-off byte-identity; the per-host `_active` invariant preserved [pool-above-host, not
  relaxed]; bounded + contained; host/loop/gateway/event unchanged; principal-id public-safety) before
  commit — Workflow if available, else MANUAL (run the full pytest and the workflow at different times).
  Commit only on a clean review / GO; fix + re-verify FRESH otherwise.
- Additive; ADR 0009 (pool-above-host); the G20 platform tail (fairness/quota/many-writer/distributed)
  deferred.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
