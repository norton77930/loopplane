# Contract: JWKS Unknown-Kid Refresh Hardening

Bound the 056 `_JwksResolver` unknown-kid refresh so a spray cannot amplify upstream IdP fetches.
Additive; confined to `webapi/auth_jwt.py`; default-safe; the legit path preserved. P1 (no ADR).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `_JwksResolver(refresh_min_interval=…)` | `float = 60.0` | + `_last_refresh`, an `anyio.Lock`, a bounded negative cache. |
| `jwt_authenticator(refresh_min_interval=…)` | `float = 60.0` | forwarded; default-safe. |

## Behavior

| Case | Result |
| ---- | ------ |
| Known cached kid (fresh) | Resolves from cache, NO fetch (byte-identical to 056). |
| N distinct unknown kids within the interval (fresh cache) | ≤ 1 network refresh; the rest rejected (`None`) without a fetch. |
| Concurrent unknown-kid burst | ONE refresh (single-flight lock + re-check), not one per request. |
| Cold start / TTL-expired cache | Refreshes (always; NOT throttled). |
| Real key rotation (a new kid) | Resolved by the first refresh the throttle permits (≤ refresh_min_interval). |
| Recently-confirmed-absent kid (cache fresh) | Short-circuits to `None` via the negative cache (no lock, no fetch). |
| `kid` is None / empty | `None` (as 056). |

## Invariants

- The legitimate verification path is preserved: a known cached kid is byte-identical (no fetch); a
  TTL-expiry / cold-start refresh ALWAYS runs (never throttled); a real rotation is detected within
  `refresh_min_interval`.
- An unknown-kid spray triggers ≤ 1 network refresh per `refresh_min_interval` (cross-request
  throttle); a concurrent burst triggers exactly one (single-flight).
- The negative-kid cache is BOUNDED (size cap / per-entry expiry) — a spray of distinct kids cannot
  grow it without limit.
- **Default-safe**: the throttle + negative cache are ON by default (`refresh_min_interval=60.0`); a
  knob tunes it. This is a security fix, NOT default-off.
- Confined to `auth_jwt.py`; no new dependency (behind the existing `loopplane[oauth]`); no
  Event-Bus/`SCHEMA_VERSION`/content change; no ADR.
- Public-safe: a throttled/rejected kid yields the same opaque `None` reject as today; the
  kid/DSN/token are never echoed.
- Out of scope: signature/iss/aud verification changes; endpoint rate-limiting; persistent
  cross-process JWKS caching; the interactive OAuth flow.
