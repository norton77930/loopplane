# Data Model: OAuth/JWT Verifier

Additive; all inside `loopplane.webapi`. No runtime/principal/event/content change. Reuses the
unit-022 `Authenticator` + `Principal`.

## jwt_authenticator (new — a factory returning an Authenticator)

`jwt_authenticator(*, …) -> Authenticator` — a host-constructed callable over the raw
`Authorization` header → `Principal | None`.

| Parameter | Type | Notes |
| --------- | ---- | ----- |
| `jwks_url` | `str \| None` | The JWKS endpoint; or derived via OIDC discovery from `issuer`. |
| `issuer` | `str` | Expected `iss`; also the OIDC-discovery base (`.well-known`) when `jwks_url` is None. |
| `audience` | `str \| list[str]` | Expected `aud`. |
| `algorithms` | `list[str]` (default `["RS256"]`) | Pinned asymmetric algs (reject `alg=none`/HS-RS confusion). |
| `principal_claim` | `str` (default `"sub"`) | The claim mapped to `Principal(id=…)`. |
| `leeway` | `int` (default small) | exp/nbf clock-skew leeway (seconds). |
| `cache_ttl` | `int` | JWKS cache TTL (seconds). |

## JWKS cache (new — internal, in the in-tree helper)

| Member | Notes |
| ------ | ----- |
| `kid → key` | cached signing keys; TTL + a bounded refresh on unknown-kid. |
| fetch | over `httpx`; bounded (timeout); OIDC discovery (`.well-known`) when configured. |

## Principal (reused — unit 022, unchanged)

`Principal(id: str)` — opaque; the verifier sets `id` from `principal_claim`. The whole ownership
chain (`make_auth_dependency`, per-route `Depends`, session ownership) is unchanged.

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| Satisfy the existing Authenticator seam; no contract change | FR-001, FR-007 |
| Validate sig (JWKS by kid) + iss + aud + exp + nbf + pinned algs; claim→Principal | FR-002 |
| Host-supplied / ships no IdP / keys / credential store | FR-003 |
| Default-off byte-identical (DENY_ALL); JWT dep import-guarded behind loopplane[oauth] | FR-004 |
| Fail-closed: any fault → deny/401, never admit; no credential echo | FR-005 |
| Negative matrix rejected; offline-tested (local keypair + in-memory JWKS) | FR-006 |
| Additive + reuse-first (wholly in webapi; reuse extra/import-guard + test harness) | FR-007 |
| Plan DECISION: PyJWT[crypto] + in-tree OIDC/JWKS helper (maintainer) | FR-008 |
