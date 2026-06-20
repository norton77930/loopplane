# Feature Specification: OAuth/JWT Verifier

**Feature Branch**: `056-oauth-verifier`

**Created**: 2026-06-20

**Status**: Draft — **plan STOPs to consult the maintainer (JWT-lib + helper-vs-BYO decision)**

**Input**: User description: "A host-supplied OAuth/JWT/OIDC token verifier behind the EXISTING unit-022 Authenticator seam: validate a bearer JWT against a JWKS (signature + issuer + audience + expiry/nbf), map a claim to a Principal. Unit 056, Tier-4 (gap G18). Additive, NO ADR (a new Authenticator implementation behind the already-designed async seam); default DENY_ALL unchanged. The JWT library + extra name and the in-tree-OIDC-helper-vs-BYO choice are a maintainer DECISION at the plan step."

## ⚠️ Boundary note (read first)

This is **additive — no ADR**. The unit-022 auth boundary already exposes the seam this needs:
`Authenticator = Callable[[str | None], Awaitable[Principal | None]]`, injected via
`create_app(host, *, authenticator=…)` (default `DENY_ALL`); its docstring explicitly anticipates
"real deployments inject their own verifier (OAuth/JWT/etc.)". A new verifier crosses **no** runtime
boundary — it lives wholly in `loopplane.webapi`, behind the shipped async seam (the async return is
what makes a JWKS network fetch feasible without a contract change). The 022 contract
(admit / deny / raise→401, no credential echo) is **inherited unchanged**. The only consult is the
**plan DECISION** (a) JWT library + optional-extra name and (b) ship a thin in-tree OIDC/JWKS helper
vs a documented BYO recipe.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An embedder verifies real OIDC tokens (Priority: P1)

An embedder fronting LoopPlane with an external IdP (Auth0/Okta/Entra/Cognito/Keycloak) configures
a verifier so a request bearing a valid OIDC/JWT access token is admitted as the corresponding
principal, and an invalid/expired/forged token is denied — without hand-writing JWT validation.

**Why this priority**: This is gap G18 — today the auth boundary ships only `DENY_ALL` + a dev/test
token map; real JWKS/issuer/audience/expiry verification is the embedder's burden. A bundled,
audited verifier is the value.

**Independent Test** (offline, a self-signed local RSA keypair + an in-memory JWKS): a token signed
by the configured key with the right issuer/audience/exp is admitted as `Principal(id=<claim>)`;
the full negative matrix (below) is denied.

**Acceptance Scenarios**:

1. **Given** a verifier configured with a JWKS + issuer + audience, **When** a request bears a valid
   signed JWT (right iss/aud, unexpired), **Then** it is admitted as the principal mapped from the
   configured claim (default `sub`).
2. **Given** the same verifier, **When** a request bears an invalid token, **Then** it is denied
   with the existing fixed 401 (no credential echoed).

---

### User Story 2 - The negative matrix is rejected (Priority: P1)

Every standard JWT failure mode is rejected: `alg=none`, an HS/RS algorithm-confusion token, a
wrong issuer, a wrong audience, an expired (`exp`) or not-yet-valid (`nbf`) token, an unknown `kid`,
and a tampered signature.

**Why this priority**: JWT validation is a well-known footgun; a verifier that is too LENIENT
(admits a forged/expired token) is the real danger and is entirely in the new code — so the
negative matrix is the load-bearing test surface.

**Independent Test**: each negative case → denied (None/raise → 401), asserted against the local
keypair + JWKS.

**Acceptance Scenarios**:

1. **Given** the verifier, **When** a token uses `alg=none` or an asymmetric/symmetric confusion,
   **Then** it is rejected (allowed algorithms are pinned to the IdP's asymmetric set).
2. **Given** the verifier, **When** `iss`/`aud` mismatch, `exp`/`nbf` fail, the `kid` is unknown, or
   the signature is tampered, **Then** each is rejected.

---

### User Story 3 - Default-off, fail-closed, offline, no leak (Priority: P2)

With no verifier injected the app still defaults to `DENY_ALL` (byte-identical). The new JWT
dependency is **import-guarded** behind an optional extra (base/non-web installs unaffected). A
verifier error (a bug, an IdP outage, a JWKS fetch failure) **fails closed** → deny/401, never
admit; failures never echo the credential.

**Why this priority**: The change must impose nothing on existing embedders + tests, and must
degrade to denial (not exposure or open-admit) under any fault.

**Independent Test**: no authenticator → `DENY_ALL` unchanged; the verifier importable only with
the extra; a JWKS-fetch failure / verifier exception → 401 (the existing fail-safe wrapper).

**Acceptance Scenarios**:

1. **Given** no authenticator configured, **When** the app handles a request, **Then** behavior is
   byte-identical to today (`DENY_ALL`).
2. **Given** a JWKS fetch failure or verifier exception, **When** a request is processed, **Then**
   it is denied (401), never admitted, with no credential echoed.

---

### Edge Cases

- **`alg=none` / HS-RS confusion**: rejected (allowed algs pinned to asymmetric).
- **unknown `kid`**: a bounded JWKS refresh (TTL cache); still-unknown → reject.
- **JWKS endpoint down / slow**: bounded fetch (timeout) → fail-closed deny; cache reduces request-
  path latency.
- **clock skew on exp/nbf**: a small configurable leeway (standard).
- **no extra installed**: the verifier import fails clearly (the optional-extra guard); base install
  + non-OAuth embedders unaffected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide a host-constructed verifier that satisfies the EXISTING `Authenticator` seam
  (`Callable[[str | None], Awaitable[Principal | None]]`) — no new seam, no `create_app` /
  `Principal` / ownership contract change.
- **FR-002**: The verifier MUST validate a bearer JWT: signature against a **JWKS** (resolved by
  `kid`, fetched + TTL-cached), **issuer**, **audience**, **expiry (`exp`) + not-before (`nbf`)**
  (with a small configurable leeway), and **pinned allowed algorithms** (reject `alg=none` +
  HS/RS confusion). A valid token maps a configured claim (default `sub`) to `Principal(id=…)`.
- **FR-003**: The verifier MUST be **host-supplied / offline-by-config**: the unit ships NO IdP, NO
  credential store, NO bundled keys — discovery URL / issuer / audience / JWKS are embedder-supplied.
- **FR-004**: The feature MUST be **default-off / byte-identical**: with no authenticator injected
  the app still defaults to `DENY_ALL`; the new JWT dependency is **import-guarded** behind a new
  optional extra (base + non-web installs unaffected).
- **FR-005**: The verifier MUST **fail closed**: any verification failure / JWKS fetch failure /
  verifier exception → deny (None/raise → the existing fixed 401), never admit; failures MUST NOT
  echo the credential (the existing fail-safe wrapper guarantees this).
- **FR-006**: The negative matrix MUST be rejected (FR-002 enumerates it) — tested with a local
  self-signed keypair + an in-memory JWKS (no network).
- **FR-007**: The capability MUST be **additive + reuse-first** — wholly inside `loopplane.webapi`
  behind the 022 seam; no change to the runtime / principal core / loop / gateway; reuse the
  existing optional-extra + import-guard conventions and the dev/test authenticator test harness.
- **FR-008** (**plan DECISION — maintainer consult**): the **JWT library + optional-extra name**
  (PyJWT[crypto] vs joserfc/authlib → e.g. `loopplane[oauth]`) and whether to ship a thin in-tree
  OIDC-discovery/JWKS-cache helper vs a documented BYO recipe MUST be confirmed by the maintainer at
  the plan step before implementing.

### Key Entities *(include if feature involves data)*

- **JWT verifier (an `Authenticator`)**: a host-constructed callable over the raw `Authorization`
  header → `Principal | None`; holds the JWKS URL / issuer / audience / allowed algs / claim / TTL.
- **JWKS cache**: a `kid`→key cache with a TTL + a bounded refresh on unknown-`kid`.
- **Principal**: the existing opaque `Principal(id: str)` (022) — unchanged; the verifier maps a
  claim to its `id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A valid OIDC/JWT (right iss/aud/exp, signed by a JWKS key) is admitted as the
  claim-mapped principal in 100% of covered scenarios.
- **SC-002**: Every negative-matrix case (`alg=none`, HS/RS confusion, wrong iss/aud, expired, nbf,
  unknown kid, tampered sig) is rejected in 100% of covered scenarios; all denials are the fixed 401
  with no credential echo.
- **SC-003**: With no authenticator, behavior is byte-identical to today (`DENY_ALL`); the JWT dep is
  import-guarded (base/non-web installs + the existing suite pass unchanged).
- **SC-004**: Verifier/JWKS faults fail closed (deny), never admit; offline-tested (local keypair +
  in-memory JWKS, no network).

## Assumptions

- Reuses the unit-022 `Authenticator` async seam + `Principal` + the fail-safe 401 wrapper +
  `make_auth_dependency` + the ownership chain (all unchanged); reuses `httpx` (the `net` extra) for
  JWKS fetch rather than adding an HTTP client; reuses the optional-extra + import-guard conventions.
- The unit ships NO IdP / keys / credential store. JWKS/issuer/audience are embedder config.
- **Plan DECISION (maintainer consult, FR-008)**: JWT lib + extra name + in-tree-helper-vs-BYO.
- Out of scope: an interactive authorization-code / browser login flow (token-in is assumed —
  obtaining the token is the embedder's IdP integration); opaque-token introspection; session
  cookies; multi-IdP federation beyond a configured issuer set.
- Default-off; fail-closed; offline-testable; public-safe (no credential echo, VII). Per
  Constitution IX the concept is borrowed from the reference harnesses but re-derived.
