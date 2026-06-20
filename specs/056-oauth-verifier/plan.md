# Implementation Plan: OAuth/JWT Verifier

**Branch**: `056-oauth-verifier` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/056-oauth-verifier/spec.md`

**Maintainer DECISION (consulted at plan, FR-008)**: **JWT library = `PyJWT[crypto]`** behind a new
**`loopplane[oauth]`** optional extra; **ship a thin in-tree OIDC-discovery + JWKS-cache helper**
(reuse `httpx`). Additive — **no ADR** (a new `Authenticator` implementation behind the shipped
unit-022 async seam; crosses no runtime boundary).

## Summary

Add a host-constructed JWT/OIDC verifier that satisfies the EXISTING unit-022 `Authenticator` seam
(`auth.py:31` — `Callable[[str | None], Awaitable[Principal | None]]`, injected via
`create_app(authenticator=…)`, default `DENY_ALL`). A new `jwt_authenticator(*, jwks_url | issuer,
audience, …)` returns an `Authenticator` that: parses `Bearer <jwt>`, resolves the signing key by
`kid` from a JWKS (fetched + TTL-cached via a thin in-tree OIDC/JWKS helper over `httpx`), verifies
the signature with **pinned asymmetric algorithms** (reject `alg=none` + HS/RS confusion), validates
`iss` / `aud` / `exp` / `nbf` (small leeway), and maps a configured claim (default `sub`) to
`Principal(id=…)`. Any failure → `None`/raise → the existing `make_auth_dependency` fixed 401 (no
credential echo). PyJWT[crypto] + httpx are **import-guarded** behind `loopplane[oauth]`; with no
authenticator injected the app still defaults to `DENY_ALL` (byte-identical). Wholly inside
`loopplane.webapi`; no runtime/principal/loop/gateway change.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: NEW optional extra `loopplane[oauth] = ["pyjwt[crypto]>=2.8",
"httpx>=0.27"]` (PyJWT for JWT verify; `cryptography` transitively for RS/ES; `httpx` for JWKS
fetch — same client the `net` extra uses). Import-guarded (the `webapi`/`net` import-guard pattern).

**Storage**: in-memory JWKS cache (`kid`→key, TTL + bounded refresh on unknown-kid). No persistence.

**Testing**: pytest, **offline** — a local self-signed RSA keypair + an in-memory JWKS (no network):
the positive path (valid token → principal) + the full negative matrix (alg=none, HS/RS confusion,
wrong iss/aud, expired, nbf, unknown kid, tampered sig) → denied; default-off (`DENY_ALL`); a
JWKS-fetch failure → fail-closed 401.

**Target Platform**: the web/API host (`loopplane.webapi`).

**Constraints**: additive behind the 022 seam (no contract change); default-off byte-identical; the
new deps import-guarded behind `loopplane[oauth]`; fail-closed; public-safe (no credential echo,
VII); reuse-first. No ADR. Out of scope: interactive authorization-code/browser flow.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008. ✅
- **III/IV. Boundary**: No runtime boundary crossed — the verifier lives wholly in `loopplane.webapi`
  behind the already-shipped `Authenticator` async seam; the runtime/principal core is untouched. ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus**: No event/schema/content change. ✅
- **VII. Public-safe**: Ships no IdP/keys/credential store; denials never echo the credential (the
  existing fail-safe wrapper). ✅
- **IX. Reference-not-clone**: The verifier concept is borrowed but re-derived against this seam. ✅
- **X. Testable Evolution**: Additive; default-off byte-identical; reversible (delete the verifier +
  extra); offline-tested. ✅

**Result**: PASS — additive, **no ADR**, no breaking 022/001 contract change. The only consult was
the plan DECISION (PyJWT[crypto] + in-tree helper, maintainer-approved). Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/056-oauth-verifier/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/oauth-verifier.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/webapi/auth_jwt.py   # NEW: jwt_authenticator(...) -> Authenticator + the in-tree
                                   #   OIDC-discovery/JWKS-cache helper; import-guards pyjwt + httpx
src/loopplane/webapi/__init__.py   # MODIFIED: export jwt_authenticator (additive __all__)
pyproject.toml                     # MODIFIED: + [project.optional-dependencies] oauth = [
                                   #   "pyjwt[crypto]>=2.8", "httpx>=0.27" ]
docs/api-reference.md              # MODIFIED: + jwt_authenticator under loopplane.webapi
tests/unit/test_oauth_verifier.py  # NEW: offline positive + the full negative matrix + default-off
```

**Structure Decision**: Localize the optional import in a sibling `auth_jwt.py` (so importing
`loopplane.webapi.auth` stays dependency-free; `jwt_authenticator` imports pyjwt/httpx lazily/guarded
and is re-exported from `webapi/__init__`). The verifier returns the EXISTING `Authenticator` type —
`create_app`, `make_auth_dependency`, the per-route `Depends`, and the `Principal.id` ownership chain
are all unchanged. The in-tree helper does OIDC discovery (optional `.well-known`) + a `kid`→key TTL
cache with a bounded refresh on unknown-kid. Default `DENY_ALL` unchanged → byte-identical.

## Complexity Tracking

> No unjustified complexity. A new `Authenticator` behind the shipped async seam + an import-guarded
> optional extra; no contract change, no ADR. The security-critical surface (the negative matrix) is
> covered by an offline test matrix, not new architecture.
