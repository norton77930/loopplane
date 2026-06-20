# Research: JWKS Unknown-Kid Refresh Hardening

P1 (no ADR). A security hardening of the 056 `_JwksResolver`. No open `NEEDS CLARIFICATION`.

## The vulnerability (056 follow-up)

`_JwksResolver.get_key` refreshes (an httpx fetch to the IdP) on EVERY unknown `kid`, and an unknown
kid bypasses the TTL (`if kid in keys and now < expiry` only short-circuits a KNOWN kid). So a spray
of random kids ⇒ one upstream fetch per request: bounded per-request, **unbounded in aggregate** — an
amplification / DoS vector.

## Decision 1 — A cross-request refresh throttle

**Decision**: Track `_last_refresh` (monotonic); an unknown-kid-driven refresh runs only when
`now - _last_refresh >= refresh_min_interval`. A TTL-expiry / cold-start refresh (`now >= _expiry`) is
NOT throttled (it must always run). Default `refresh_min_interval = 60.0` (≤ `cache_ttl`).

**Rationale**: Bounds the spray to ≤ 1 fetch per interval while keeping rotation-detection latency ≤
~1 min. The legit TTL refresh path is untouched.

**Alternatives**: throttle by `_expiry` only (rejected — an unknown kid within a fresh window would
never refresh, so a real rotation mid-TTL would be missed until expiry, up to `cache_ttl`).

## Decision 2 — Single-flight

**Decision**: An `anyio.Lock` serializes the refresh; after acquiring, re-check the cache hit (another
coroutine may have refreshed) before deciding to refresh. A concurrent unknown-kid burst ⇒ one fetch.

**Rationale**: Without it, a concurrent burst all pass the pre-lock check and each fetch; the lock +
re-check collapses them to one.

## Decision 3 — A bounded negative-kid cache

**Decision**: A kid still absent after a fresh refresh is remembered (with a per-entry expiry = the
next permitted refresh time) in a BOUNDED structure; while the cache is fresh, a request for a
negatively-cached kid short-circuits to `None` without taking the lock or fetching.

**Rationale**: Cheap fast-path for repeated bad kids; bounded so a spray of distinct kids cannot grow
it without limit (cap the size / evict by expiry).

## Decision 4 — Default-safe (not default-off)

**Decision**: The throttle + negative cache are ON by default (it is a security fix). The legitimate
path is byte-identical for a known cached kid (no fetch); a TTL/cold-start refresh always runs; a real
new kid after rotation is resolved by the first throttle-permitted refresh. A `refresh_min_interval`
knob tunes it (set very large ≈ effectively disable; the legit path still works).

**Rationale**: A security fix that defaulted OFF would leave the vulnerability open; the default must
close it while preserving real verification.

## Out of scope

Changing signature/issuer/audience verification; a rotating-key push strategy; endpoint-level rate
limiting (a deployment concern); persistent cross-process JWKS caching; the interactive OAuth flow
(deferred). No new public package (the `refresh_min_interval` knob is a new kwarg on the existing
`jwt_authenticator`, already exported — confirm the api-reference needs no change).
