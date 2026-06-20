# Tasks: OAuth/JWT Verifier

**Feature**: 056-oauth-verifier | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, no ADR — a new `loopplane.webapi.auth_jwt` verifier (`jwt_authenticator`) + an
in-tree OIDC/JWKS helper behind the EXISTING unit-022 `Authenticator` seam; a new import-guarded
`loopplane[oauth]` extra (PyJWT[crypto] + httpx); default-off `DENY_ALL` byte-identical. Maintainer
DECISION settled (PyJWT[crypto] + in-tree helper). **Security-critical**: the negative matrix is the
load-bearing test surface.

**Tests**: requested (security matrix mandatory).

## Phase 1: Dependency (Foundational)

- [ ] T001 Add the optional extra to `pyproject.toml` `[project.optional-dependencies]`:
  `oauth = ["pyjwt[crypto]>=2.8", "httpx>=0.27"]` (alongside anthropic/net/openai/web). No change to
  base/runtime deps.

## Phase 2: The verifier + in-tree helper (P1) 🎯

- [ ] T002 Create `src/loopplane/webapi/auth_jwt.py`: `jwt_authenticator(*, issuer, audience,
  jwks_url=None, algorithms=["RS256"], principal_claim="sub", leeway=…, cache_ttl=…) ->
  Authenticator` (returns the EXISTING `loopplane.webapi.auth.Authenticator` type). It parses
  `Bearer <jwt>`, reads the header `kid`, resolves the signing key from a JWKS via an in-tree helper
  (OIDC discovery of `.well-known/openid-configuration` → `jwks_uri` when `jwks_url` is None; a
  `kid`→key TTL cache with a bounded refresh on unknown-kid; fetch over `httpx` with a timeout),
  verifies the signature with PyJWT pinning `algorithms` (reject `alg=none` + HS/RS confusion),
  validates `iss` / `aud` / `exp` / `nbf` (leeway), and returns `Principal(id=<principal_claim>)`.
  Any failure → return `None` (or raise → the existing 401). **IMPORT-GUARD** `jwt` (PyJWT) + `httpx`
  here (a clear error if the `oauth` extra is absent) so `loopplane.webapi.auth` stays
  dependency-free. Never log/echo the token.

## Phase 3: Export + docs (P1)

- [ ] T003 Re-export `jwt_authenticator` from `src/loopplane/webapi/__init__.py` (additive `__all__`,
  alongside `Authenticator`/`Principal`/`token_authenticator`) and add it to `docs/api-reference.md`
  under `loopplane.webapi` (so the api-reference bijection stays exact).

## Phase 4: Tests (P1/P2) — security matrix

- [ ] T004 Create `tests/unit/test_oauth_verifier.py` (OFFLINE — a locally-generated self-signed RSA
  keypair + an in-memory JWKS served to the helper via a stub/monkeypatched fetch; NO network),
  using `pytest.importorskip` for the `oauth` extra: (a) POSITIVE — a JWT signed by the local key
  with the right iss/aud, unexpired, allowed alg → admitted as `Principal(id=<sub>)`; (b) the FULL
  NEGATIVE matrix → each denied: `alg=none`, HS/RS confusion (an HS256 token where RS256 is
  expected), wrong `iss`, wrong `aud`, expired `exp`, `nbf` in the future, unknown `kid`, tampered
  signature; (c) DEFAULT-OFF — `create_app` with no authenticator still `DENY_ALL` (byte-identical;
  reuse the existing webapi auth test harness); (d) FAIL-CLOSED — a JWKS fetch fault / verifier
  exception → deny (401), never admit; (e) the principal-claim mapping. Assert denials carry no
  credential echo.

## Phase 5: Gates

- [ ] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-off byte-identity). Confirm: `test_public_safety` +
  the api-reference-bijection test pass (the new `jwt_authenticator` export documented); the base
  install is unaffected (the `oauth` extra import-guarded). The negative-path matrix all green.

## Dependencies

- T001 → T002 (the import-guard needs the extra). T002 → T003, T004. All → T005 (gates last).

## Implementation strategy

- Well-scoped + security-critical — a fork subagent MAY do it (mirror 048-055); then the four gates +
  `test_public_safety` + the api-reference bijection + an adversarial verify (the negative matrix
  completeness, alg-pinning / no alg=none / no HS-RS confusion, fail-closed, default-off DENY_ALL
  byte-identity, import-guard, no credential echo) run before commit — Workflow if available, else
  MANUAL. Commit only on a clean review / GO.
- Additive; no ADR; no runtime/principal/loop/gateway change.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 2 low (informational). 100% requirement
coverage (FR-001..FR-008 and SC-001..004 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ data-model ↔ contract ↔ tasks agree (jwt_authenticator
satisfying the EXISTING unit-022 `Authenticator` seam; PyJWT[crypto] import-guarded behind the new
`loopplane[oauth]` extra; the in-tree OIDC/JWKS helper; pinned asymmetric algs; iss/aud/exp/nbf
validation; claim→Principal; default-off `DENY_ALL` byte-identity; fail-closed; the full negative
matrix). **Additive — no ADR**: crosses no runtime boundary (wholly in `loopplane.webapi`, behind
the shipped async seam); no 022/001 contract change; no event/schema/content change. No Constitution
violation (I/III/IV/V/VI/VII/IX/X). The maintainer plan DECISION (FR-008) is SETTLED (PyJWT[crypto]
+ in-tree helper) — no re-consult. Low notes are informational: (1) the NEGATIVE-MATRIX completeness
(T004) is load-bearing — a too-lenient verifier is the real risk; verify each case (esp. alg=none +
HS/RS confusion) at implement; (2) the import-guard (T002) must keep `loopplane.webapi.auth`
dependency-free + give a clear error when the `oauth` extra is absent. **Cleared for
`/speckit-implement`.**
