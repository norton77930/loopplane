# Data Model: JWKS Unknown-Kid Refresh Hardening

Additive; confined to the 056 `_JwksResolver` in `webapi/auth_jwt.py`. No event/content/schema change.
P1 (no ADR).

## `_JwksResolver` (modified — additive)

| Field (new) | Type | Notes |
| ----------- | ---- | ----- |
| `_refresh_min_interval` | `float` | min seconds between unknown-kid-driven refreshes (ctor; default 60.0). |
| `_last_refresh` | `float` | monotonic timestamp of the last refresh (init 0.0). |
| `_refresh_lock` | `anyio.Lock` | single-flight serialization of the refresh. |
| `_negative` | `dict[str, float]` (bounded) | kid → expiry; recently-confirmed-absent kids. |

| Method | Change |
| ------ | ------ |
| `__init__` | + `refresh_min_interval: float = 60.0` param + the new fields. |
| `get_key(kid)` | throttle + single-flight + negative-cache (see the flow below); a cache HIT is byte-identical. |
| `_refresh()` | also sets `_last_refresh = now` (alongside `_expiry`). |

## `get_key` flow

```text
if not kid: return None
now = monotonic()
if kid in _keys and now < _expiry: return _keys[kid]          # legit cache hit (byte-identical)
if now < _expiry and _negative.get(kid, 0) > now: return None # fresh negative cache → reject, no fetch
async with _refresh_lock:                                     # single-flight
    now = monotonic()
    if kid in _keys and now < _expiry: return _keys[kid]      # re-check (another coro refreshed)
    cache_expired = now >= _expiry
    if cache_expired or (now - _last_refresh) >= _refresh_min_interval:
        await _refresh()                                      # sets _keys/_expiry/_last_refresh
        if kid in _keys: return _keys[kid]
    _remember_absent(kid, now)                                # bounded negative cache
    return None
```

## `jwt_authenticator` (modified — additive)

| Surface | Type | Notes |
| ------- | ---- | ----- |
| `jwt_authenticator(refresh_min_interval=…)` | `float = 60.0` | forwarded to `_JwksResolver`; default-safe. |

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| cross-request throttle: unknown-kid refresh ≤ once / refresh_min_interval | FR-001 |
| single-flight: a concurrent burst shares one refresh (lock + re-check) | FR-002 |
| bounded negative-kid cache short-circuits a recent absent kid | FR-003 |
| legit path preserved: cache hit byte-identical; TTL/cold-start refresh always; rotation resolved | FR-004 |
| default-safe (throttle on, default 60.0); confined to auth_jwt.py; no dependency; no ADR | FR-005 |
| public-safe: opaque reject; no kid/DSN/token echoed | FR-006 |
