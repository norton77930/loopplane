# Tasks: JWKS Unknown-Kid Refresh Hardening

**Feature**: 067-jwks-hardening | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive security hardening of the 056 `_JwksResolver`, confined to `webapi/auth_jwt.py`:
a cross-request refresh throttle + single-flight + a bounded negative-kid cache. No ADR. Default-safe;
the legit verification path preserved. P1 (batch 064–072, 4/9, the last P1).

**Tests**: requested (offline; a counting fake `_fetch_jwks` — NO real network).

## Phase 1: The hardened resolver (P1) 🎯

- [ ] T001 In `src/loopplane/webapi/auth_jwt.py` `_JwksResolver.__init__`: add
  `refresh_min_interval: float = 60.0` param + the new fields: `_refresh_min_interval`,
  `_last_refresh: float = 0.0`, `_refresh_lock = anyio.Lock()`, `_negative: dict[str, float] = {}`
  (bounded). Import `anyio` at module top (already a dependency).
- [ ] T002 Rewrite `_JwksResolver.get_key(kid)` with the throttle + single-flight + negative-cache
  (per data-model): (1) `not kid` → None; (2) cache HIT (`kid in _keys and now < _expiry`) → return
  [byte-identical]; (3) fresh-cache negative-cache hit → None (no lock, no fetch); (4) under
  `_refresh_lock`: re-check the cache hit; refresh ONLY when `cache_expired` (`now >= _expiry`,
  always — TTL/cold-start) OR (`now - _last_refresh >= _refresh_min_interval`); after a refresh return
  `_keys[kid]` if present; (5) else `_remember_absent(kid, now)` (bounded) + return None. In
  `_refresh()` set `_last_refresh = time.monotonic()` (alongside `_expiry`). Add a small
  `_remember_absent` that caps the negative dict (evict expired / oldest) so a spray can't grow it.

## Phase 2: The config knob (P1)

- [ ] T003 In `jwt_authenticator(...)`: add `refresh_min_interval: float = 60.0` kwarg, forward it to
  `_JwksResolver(refresh_min_interval=…)`. Document it (default-safe). Confirm no api-reference change
  is needed (the kwarg is on the already-exported `jwt_authenticator`; if the function is enumerated,
  the bijection is by name not signature — verify the api-reference test stays green).

## Phase 3: Tests (P1) — offline, no network

- [ ] T004 Add `tests/<unit>/test_jwks_hardening.py` (a `_JwksResolver` subclass / monkeypatch with a
  counting fake `_fetch_jwks` returning an in-memory JWKS — NO httpx call; `pytestmark =
  pytest.mark.anyio`): (a) spray bound — N distinct unknown kids within the interval → fetch counter
  ≤ 1, each → None; (b) single-flight — a concurrent burst of unknown-kid `get_key`s (anyio task
  group) → exactly one fetch; (c) legit cache hit — a known kid → resolves, zero fetches; (d) cold
  start / expired cache → refreshes (not throttled); (e) rotation — advance the clock past
  refresh_min_interval, a new kid → the first request refreshes + resolves; (f) negative cache — a
  repeated absent kid (fresh cache) → no extra fetch, bounded; (g) public-safe — a rejected/throttled
  kid → None, no kid/DSN/token in any message. Use a monotonic-clock injection or monkeypatch
  `time.monotonic` for the interval/rotation tests. Benign placeholders only.

## Phase 4: Gates

- [ ] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full). Confirm: the existing 056 auth/security suite passes (the legit path is
  preserved); the structural audits (`test_public_safety`, `test_no_execution_path_outside_the_gateway`)
  + the events serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the api-reference bijection pass;
  `import loopplane.webapi.auth_jwt` works WITHOUT the oauth extra (the PyJWT/httpx imports stay
  guarded). Do NOT run the full pytest concurrently with a verify Workflow (MCP load flake).

## Dependencies

- T001 → T002 (the resolver fields then the flow) → T003 (the knob) → T004 (tests) → T005 (gates).

## Implementation strategy

- A focused change inside `_JwksResolver` + the `jwt_authenticator` ctor + tests. May be done inline
  or via a fork; then the four gates + the structural audits + the events/api-reference tests + a
  focused adversarial review (the spray bound [≤1 fetch/interval]; single-flight [one fetch for a
  concurrent burst]; the legit path preserved — cache hit byte-identical, TTL/cold-start refresh not
  throttled, rotation resolved; the negative cache is bounded; public-safety; no dependency/schema
  change) before commit. Commit only on a clean review / GO; fix + re-verify FRESH otherwise.
- Additive; default-safe; P1; no ADR.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
