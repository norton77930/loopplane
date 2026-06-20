# Quickstart / Validation: OAuth/JWT Verifier

See [contracts/oauth-verifier.md](contracts/oauth-verifier.md) + [data-model.md](data-model.md). A
host-supplied JWT/OIDC verifier behind the unit-022 `Authenticator` seam; additive, default-off
(`DENY_ALL`), no ADR. **PyJWT[crypto] + an in-tree OIDC/JWKS helper** behind `loopplane[oauth]`.

## Install the extra (for the verifier + its tests)

```powershell
pip install -e ".[oauth]"   # pyjwt[crypto] + httpx
```

## Run the unit tests (offline — local keypair + in-memory JWKS)

```powershell
pytest tests/unit/test_oauth_verifier.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; with no authenticator the app still defaults to `DENY_ALL` (the existing webapi/auth
tests pass unchanged). Base/non-oauth installs are unaffected (the JWT dep is import-guarded).

## Validation scenarios (mirror the acceptance scenarios)

1. **Valid token → principal** — a JWT signed by the local key (right iss/aud, unexpired, allowed
   alg) → admitted as `Principal(id=<sub>)`. (FR-001/002, SC-001)
2. **Negative matrix → denied** — `alg=none`, HS/RS confusion, wrong iss, wrong aud, expired, nbf
   not reached, unknown kid, tampered signature → each denied (fixed 401, no echo). (FR-002/006, SC-002)
3. **Default-off byte-identity** — no authenticator → `DENY_ALL` unchanged; the JWT dep is
   import-guarded. (FR-004, SC-003)
4. **Fail-closed** — a JWKS-fetch failure / verifier exception → deny (401), never admit. (FR-005, SC-004)
5. **Claim mapping** — `principal_claim` maps the configured claim to `Principal.id`. (FR-002)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the public-safety + api-reference-bijection tests (the new `jwt_authenticator` export documented
in docs/api-reference.md under `loopplane.webapi`).
