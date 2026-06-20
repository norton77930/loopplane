# Feature Specification: JWKS Unknown-Kid Refresh Hardening

**Feature Branch**: `067-jwks-hardening`

**Created**: 2026-06-21

**Status**: Draft — P1 (review backlog batch 064–072, unit 4/9, the last P1)

**Input**: User description: "P1: bound the 056 unknown-kid JWKS refresh — a negative-kid cache + a cross-request refresh throttle so a random-kid spray can't amplify upstream IdP fetches. Additive to webapi/auth_jwt.py behind loopplane[oauth]; default-safe. Touches auth_jwt.py only."

## ⚠️ Boundary note (read first)

056's `_JwksResolver.get_key(kid)` refreshes the JWKS (an upstream IdP fetch over httpx) on EVERY
unknown `kid` — and an unknown kid BYPASSES the TTL cache. So an attacker spraying random `kid`s
triggers one upstream fetch PER request: bounded per-request but **unbounded in aggregate** — an
amplification / DoS vector against the IdP. This unit bounds it, confined to `webapi/auth_jwt.py`
(behind the existing `loopplane[oauth]` extra): a **cross-request refresh throttle** (≤ 1 network
refresh per interval), a **single-flight** refresh (concurrent unknown-kid requests share one fetch),
and a short **negative-kid cache** (a recently-confirmed-absent kid short-circuits without a fetch).
**Default-safe** (the throttle is ON with a sensible default) — NOT default-off, because it is a
security fix; the LEGITIMATE verification path is preserved (a known kid is byte-identical; a real
new kid after a key rotation is still picked up by the first refresh in the interval). No new
dependency; touches `auth_jwt.py` only; public-safe. No ADR.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A random-kid spray cannot amplify IdP fetches (Priority: P1)

A burst of requests each carrying a different unknown `kid` triggers AT MOST one upstream JWKS fetch
per throttle interval (and a single fetch for a concurrent burst), instead of one fetch per request.

**Why this priority**: This is the security fix — it removes the aggregate amplification vector the
056 follow-up flagged.

**Independent Test** (offline; a fake `_fetch_jwks` counting calls): fire N requests with N distinct
unknown kids within the interval → the fetch counter is ≤ 1 (not N); each is rejected (no key); a
concurrent burst → a single fetch (single-flight).

**Acceptance Scenarios**:

1. **Given** the resolver has refreshed recently, **When** many distinct unknown kids arrive within
   the throttle interval, **Then** at most one further network refresh occurs; the unknown kids are
   rejected (`None`) without per-request fetches.
2. **Given** a concurrent burst of unknown-kid requests, **When** they race, **Then** they share a
   single in-flight refresh (single-flight), not one fetch each.

---

### User Story 2 - Legitimate verification is preserved (Priority: P1)

A known `kid` (in the cache) verifies with no fetch (byte-identical to 056); a genuinely new `kid`
after a key rotation is still resolved by the first refresh allowed in the interval.

**Why this priority**: The hardening must not break real verification — a known key must still work,
and a real rotation must still be picked up.

**Independent Test**: a known kid → resolves from cache, zero fetches; after a rotation (a new kid +
the throttle interval permits a refresh) → the first request refreshes and resolves the new key.

**Acceptance Scenarios**:

1. **Given** a cached known kid, **When** it is verified, **Then** it resolves with no network fetch
   (byte-identical to 056's cache hit).
2. **Given** a real key rotation, **When** the first unknown-kid request arrives and the throttle
   permits a refresh, **Then** the refresh fetches the new JWKS and resolves the new kid.

---

### Edge Cases

- **TTL expiry**: a legitimate TTL-expiry refresh is unaffected (the throttle bounds only the
  unknown-kid-driven refreshes; an expired cache still refreshes on a known-kid miss as before, or
  the throttle interval ≤ cache_ttl is configured so it never blocks a legit TTL refresh).
- **negative-kid cache**: a kid confirmed absent by a fresh refresh is remembered briefly →
  subsequent requests for it short-circuit to `None` without re-entering the throttle/refresh.
- **single-flight**: a concurrent unknown-kid burst shares ONE refresh (an `anyio.Lock` /
  in-flight marker), not one per coroutine.
- **public-safety**: the kid / DSN / token are never echoed in errors or logs; a rejected kid yields
  the same opaque `None` (→ the 056 fail-closed `DENY_ALL`-style reject) as today.
- **default-safe**: the throttle + negative cache are ON by default with a sensible interval; a config
  knob tunes the interval (and can widen it); the legit path is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add a **cross-request refresh throttle** to `_JwksResolver`: an unknown-kid-driven
  network refresh occurs at most once per `refresh_min_interval`; within that interval, an unknown
  kid is rejected (`None`) WITHOUT a network fetch.
- **FR-002**: Add a **single-flight** guard so a concurrent burst of unknown-kid requests shares ONE
  in-flight refresh (an `anyio.Lock` / in-flight future), not one fetch per request.
- **FR-003**: Add a short **negative-kid cache**: a kid confirmed absent immediately after a fresh
  refresh is remembered (bounded) and short-circuits to `None` for a brief window without a fetch.
- **FR-004**: Preserve the LEGITIMATE path: a known cached kid resolves with NO fetch (byte-identical
  to 056); a real new kid after a rotation is resolved by the first refresh the throttle permits; a
  normal TTL-expiry refresh is unaffected.
- **FR-005**: **Default-safe** — the throttle + negative cache are ON by default with a sensible
  `refresh_min_interval`; a config knob (on `jwt_authenticator` / the resolver) tunes it. Confined to
  `webapi/auth_jwt.py`; no new dependency (behind the existing `loopplane[oauth]`); no ADR.
- **FR-006**: Public-safe — the kid / DSN / token are never echoed; a rejected/throttled kid yields
  the same opaque reject as today (no information leak about why).

### Key Entities *(include if feature involves data)*

- **`_JwksResolver` (extended)**: + `refresh_min_interval`, a last-refresh timestamp, a single-flight
  lock, and a bounded negative-kid set/cache.
- **`jwt_authenticator(refresh_min_interval=…)`**: the optional tuning knob (default a safe value).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: N distinct unknown kids within the interval cause ≤ 1 network fetch (not N); a
  concurrent burst causes 1 fetch (single-flight) — verified by a call-counting fake JWKS.
- **SC-002**: A known cached kid resolves with zero fetches (byte-identical to 056); a real rotation
  is still resolved by the first throttle-permitted refresh.
- **SC-003**: No new dependency / Event-Bus / SCHEMA change; confined to `auth_jwt.py`; public-safe;
  the four gates + the existing 056 auth suite pass.

## Assumptions

- Reuses 056's `_JwksResolver` + `jwt_authenticator` + the import-guarded PyJWT/httpx + the
  fail-closed reject (an unresolved kid → `None` → no `Principal`).
- The `refresh_min_interval` default is chosen so it never blocks a legitimate TTL-driven refresh
  (e.g. ≤ `cache_ttl`) while bounding the unknown-kid spray; the plan picks the exact default.
- **Out of scope**: changing the signature/issuer/audience verification; rotating-key strategy beyond
  the throttle; rate-limiting the whole auth endpoint (that is a deployment concern); persistent
  cross-process JWKS caching; the interactive OAuth flow (deferred). 
- Additive; default-safe (a security fix, not default-off); confined to `auth_jwt.py`; public-safe;
  offline-testable. No ADR (a hardening of the existing 056 seam, no new boundary).
