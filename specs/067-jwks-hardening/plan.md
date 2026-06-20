# Implementation Plan: JWKS Unknown-Kid Refresh Hardening

**Branch**: `067-jwks-hardening` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/067-jwks-hardening/spec.md`

**Boundary**: P1 (review-backlog batch 064–072, 4/9, the last P1). A security hardening of the 056
`_JwksResolver`, confined to `webapi/auth_jwt.py`; **no ADR**.

## Summary

Bound the unknown-`kid` JWKS refresh in `_JwksResolver` so a random-kid spray cannot make one upstream
IdP fetch per request. Add three mechanisms (all inside `_JwksResolver`): a **cross-request refresh
throttle** (`refresh_min_interval`; an unknown-kid-driven refresh ≤ once per interval), **single-flight**
(an `anyio.Lock` + re-check so a concurrent burst shares one refresh), and a short **negative-kid
cache** (a recently-confirmed-absent kid short-circuits to `None` without re-entering the refresh
path). The legitimate path is preserved: a known cached kid is byte-identical (no fetch); a TTL-expiry
/ cold-start refresh always runs; a real new kid after a rotation is resolved by the first refresh the
throttle permits. **Default-safe** (the throttle is ON with a sensible `refresh_min_interval=60.0`),
NOT default-off — it is a security fix. Confined to `auth_jwt.py`; no new dependency; public-safe; no
ADR.

## Technical Context

**Language/Version**: Python 3.11+; PyJWT + httpx (the existing import-guarded `loopplane[oauth]`);
`anyio` (already a dependency).

**Primary Dependencies**: none new — extends 056's `_JwksResolver`/`jwt_authenticator`.

**Storage**: none (in-memory cache, as 056).

**Testing**: pytest, offline (a fake `_fetch_jwks` counting calls + an in-memory JWKS — the 056 test
pattern): N distinct unknown kids within the interval → ≤ 1 fetch; a concurrent burst → 1 fetch
(single-flight); a known kid → 0 fetches (cache hit); a rotation → resolved by the first permitted
refresh; an expired-cache/cold-start → refreshes.

**Target Platform**: cross-platform library (web host).

**Constraints**: additive; confined to `auth_jwt.py`; default-safe (throttle on, legit path
preserved); no new dependency; public-safe; no Event-Bus/SCHEMA change; no ADR.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006. ✅
- **III. Bounded cost/abuse**: caps the aggregate IdP-fetch amplification an attacker can induce. ✅
- **IV. Boundary**: confined to the 056 `_JwksResolver` in `webapi`; no controller/loop/gateway
  change. ✅
- **V. Tool Gateway**: N/A — auth seam, no tool/execution path. ✅
- **VI. Event Bus**: no event/`SCHEMA_VERSION`/content change. ✅
- **VII. Public-safe**: a throttled/rejected kid yields the same opaque reject (`None`); the
  kid/DSN/token are never echoed. ✅
- **X. Testable Evolution**: Additive; the legit path preserved; offline-tested; reversible (widen
  the interval to ∞ ≈ never throttle, or the knob disables it). ✅

**Result**: PASS — a security hardening of the existing 056 seam; default-safe; no ADR. Complexity
Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/067-jwks-hardening/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/jwks-hardening.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/webapi/auth_jwt.py    # MODIFIED: _JwksResolver gains refresh_min_interval +
                                    #   _last_refresh + an anyio.Lock (single-flight) + a bounded
                                    #   negative-kid cache; get_key throttles the unknown-kid refresh
                                    #   (TTL-expiry/cold-start refresh unaffected); jwt_authenticator
                                    #   gains refresh_min_interval (default 60.0) forwarded to it
tests/<jwks hardening tests>        # NEW (spray bound, single-flight, legit path, rotation, cold-start)
```

**Structure Decision**: All changes are inside `_JwksResolver` + the `jwt_authenticator` ctor. The
new `get_key` flow: (1) `not kid` → None; (2) cache hit (kid in keys AND `now < expiry`) → return
[byte-identical]; (3) the fresh-but-absent fast path: if the cache is fresh AND the kid is in the
negative cache (still valid) → None (no lock, no fetch); (4) under the single-flight `anyio.Lock`,
re-check the cache hit, then refresh ONLY when `cache_expired` (TTL/cold-start — always) OR the kid is
unknown AND `now - _last_refresh >= refresh_min_interval` (the throttle); `_refresh()` sets
`_keys`/`_expiry`/`_last_refresh`; (5) if still absent → add to the bounded negative cache + return
None. So: a TTL/cold-start refresh always runs; an unknown-kid spray within a fresh window triggers
≤ 1 refresh per `refresh_min_interval`; a concurrent burst shares one refresh (the lock + re-check); a
rotation is detected within `refresh_min_interval`. `refresh_min_interval` default `60.0` (≤
`cache_ttl`; bounds the spray to ≤1 fetch/min while keeping rotation-detection latency ≤ ~1 min);
exposed as a `jwt_authenticator(refresh_min_interval=…)` knob. The negative cache is bounded (a small
cap / a per-entry expiry = the next permitted refresh) so it cannot grow unbounded under a spray.

## Complexity Tracking

> A throttle + single-flight + a bounded negative cache inside the existing 056 `_JwksResolver`.
> Additive; the legit verification path preserved; confined to `auth_jwt.py`; no dependency/event/
> schema/ADR. Not a Constitution violation.
