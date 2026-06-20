# Contract: OAuth/JWT Verifier

A host-constructed `jwt_authenticator(...)` that satisfies the EXISTING unit-022 `Authenticator`
seam. Active only when the embedder injects it via `create_app(authenticator=…)`; default is
`DENY_ALL` (byte-identical). PyJWT[crypto] + httpx import-guarded behind `loopplane[oauth]`.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `loopplane.webapi.jwt_authenticator` | `(*, issuer, audience, jwks_url=None, algorithms=["RS256"], principal_claim="sub", leeway, cache_ttl) -> Authenticator` | NEW (additive `__all__`); returns the existing `Authenticator` type. |
| `loopplane[oauth]` extra | `["pyjwt[crypto]>=2.8", "httpx>=0.27"]` | NEW optional extra; import-guarded. |

## Behavior

| Case | Result |
| ---- | ------ |
| No authenticator injected (default) | `DENY_ALL` — byte-identical to today; the JWT dep is never imported. |
| Valid bearer JWT (right iss/aud, unexpired, signed by a JWKS key, allowed alg) | Admitted as `Principal(id=<principal_claim>)`. |
| `alg=none` / HS-RS confusion | Rejected (algs pinned to the asymmetric set). |
| Wrong `iss` / wrong `aud` / expired `exp` / `nbf` not reached | Rejected. |
| Unknown `kid` | One bounded JWKS refresh; still-unknown → rejected. |
| Tampered signature | Rejected. |
| JWKS endpoint down / fetch fault / verifier exception | **Fail closed** → deny (raise/None → the existing fixed 401), never admit. |
| Any denial | The existing `make_auth_dependency` 401 — no credential echoed. |

## Invariants

- Satisfies the EXISTING `Authenticator = Callable[[str | None], Awaitable[Principal | None]]` — no
  change to `create_app` / `make_auth_dependency` / `Principal` / the ownership chain (V/VI/022 intact).
- Wholly inside `loopplane.webapi`; no runtime / principal core / loop / gateway / event change.
- Default `DENY_ALL` is byte-identical; the new deps are import-guarded behind `loopplane[oauth]`
  (base + non-web installs + the existing suite unaffected).
- Fail-closed (deny on any fault); public-safe (ships no IdP/keys; never echoes the credential, VII).
- Pinned asymmetric algorithms; full claim validation (iss/aud/exp/nbf); JWKS resolved by `kid`,
  TTL-cached, bounded fetch.
- Offline-testable (local self-signed keypair + in-memory JWKS; no network). No ADR.
- Out of scope: interactive authorization-code/browser flow; opaque-token introspection.
