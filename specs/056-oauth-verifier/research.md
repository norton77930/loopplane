# Research: OAuth/JWT Verifier

The library + JWKS-strategy choices were the maintainer DECISION (FR-008, consulted at plan):
**PyJWT[crypto]** + an **in-tree OIDC/JWKS helper**. No open `NEEDS CLARIFICATION`.

## Decision 1 — JWT library = PyJWT[crypto] behind loopplane[oauth] (maintainer)

**Decision**: Use `PyJWT[crypto]` (the `crypto` extra pulls `cryptography` for RS/ES signature
verification) behind a NEW optional extra `loopplane[oauth] = ["pyjwt[crypto]>=2.8", "httpx>=0.27"]`,
import-guarded so base/non-web installs are unaffected.

**Rationale**: The most widely-used, audited, minimal Python JWT library; covers exactly what's
needed (decode + verify signature/claims, JWKS via `PyJWKClient` or `PyJWK`) with the smallest attack
surface. joserfc/authlib are heavier (full JOSE/OAuth frameworks) — deferred unless JWE/fuller JOSE
is later needed.

**Alternatives considered**: joserfc (modern JOSE, more surface); authlib (full OAuth/OIDC framework,
overkill for token verification only).

## Decision 2 — In-tree OIDC/JWKS helper (maintainer)

**Decision**: Ship a thin in-tree helper that does OIDC discovery (optional `.well-known/
openid-configuration` → `jwks_uri`) + a `kid`→key TTL cache with a bounded refresh on unknown-kid,
fetching over `httpx` (the same client the `net` extra uses). The embedder supplies issuer/audience
(or a discovery URL); the helper handles JWKS.

**Rationale**: Higher parity value — the embedder shouldn't hand-write JWKS fetch/caching. The extra
audit surface is covered by the offline negative-path test matrix.

**Alternatives considered**: a documented BYO recipe (smallest surface, but pushes JWKS plumbing onto
every embedder).

## Decision 3 — Satisfy the EXISTING 022 Authenticator seam (additive, no ADR)

**Decision**: `jwt_authenticator(...)` returns the existing `Authenticator =
Callable[[str | None], Awaitable[Principal | None]]` (auth.py:31), injected via the existing
`create_app(authenticator=…)` (app.py:90, default `DENY_ALL`). The async return is what makes a JWKS
network fetch feasible with no contract change. Failure → `None`/raise → the existing
`make_auth_dependency` fixed 401 (no credential echo). `Principal(id: str)` + the ownership chain are
unchanged.

**Rationale**: Crosses no runtime boundary → no ADR; the 022 docstring explicitly anticipates an
injected OAuth/JWT verifier. Reuse-first.

## Decision 4 — Security posture (pinned algs, full claim validation, fail-closed)

**Decision**: Pin allowed algorithms to the IdP's asymmetric set (e.g. `RS256`/`ES256`) — reject
`alg=none` and HS/RS confusion. Validate `iss` + `aud` + `exp` + `nbf` (a small configurable leeway),
resolve the key by header `kid`, bound the JWKS fetch (timeout + cache). Any verification/JWKS fault
→ deny (None/raise → 401), never admit; never echo the credential.

**Rationale**: A too-LENIENT verifier (admits forged/expired) is the real danger and is entirely in
the new code; the fail-safe wrapper already guarantees raise→401 with no echo, so a verifier bug
degrades to denial. The negative matrix is the load-bearing test surface.

## Decision 5 — Localize the optional import (auth_jwt.py)

**Decision**: Put `jwt_authenticator` + the helper in a sibling `loopplane/webapi/auth_jwt.py` (so
`loopplane.webapi.auth` stays dependency-free); import-guard pyjwt/httpx there; re-export from
`webapi/__init__`.

**Rationale**: Keeps the always-imported `auth` module dependency-free; matches the import-guard
convention (fastapi via `web`, httpx via `net`).

## Out of scope

Interactive authorization-code / browser login (token-in is assumed — obtaining the token is the
embedder's IdP integration); opaque-token introspection; session cookies; multi-IdP federation
beyond a configured issuer set.
