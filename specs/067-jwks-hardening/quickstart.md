# Quickstart / Validation: JWKS Unknown-Kid Refresh Hardening

See [contracts/jwks-hardening.md](contracts/jwks-hardening.md), [data-model.md](data-model.md). Bound
the 056 unknown-kid JWKS refresh (throttle + single-flight + negative cache), confined to
`webapi/auth_jwt.py`. Additive; default-safe; the legit path preserved; no dependency/schema/ADR.

## Run the tests

```powershell
pytest tests/ -k "jwt or jwks or auth or oauth" -q
pytest -q   # full suite (additive proof)
```

Expected: green; the existing 056 auth suite passes; SCHEMA_VERSION unchanged.

## Validation scenarios (mirror the acceptance scenarios)

1. **Spray bound** — a counting fake `_fetch_jwks`; fire N distinct unknown kids within the interval →
   the fetch counter ≤ 1; each rejected (`None`). (FR-001, SC-001)
2. **Single-flight** — a concurrent burst of unknown-kid `get_key`s → one fetch. (FR-002, SC-001)
3. **Legit cache hit** — a known kid → resolves with zero fetches (byte-identical). (FR-004, SC-002)
4. **Rotation** — a new kid + the throttle interval elapsed → the first request refreshes and
   resolves the new key. (FR-004, SC-002)
5. **Cold start / TTL expiry** — an empty/expired cache → refreshes (not throttled). (FR-004)
6. **Negative cache** — a repeated absent kid (cache fresh) → short-circuits to `None` without a
   fetch; the cache is bounded. (FR-003)
7. **Public-safe** — a throttled/rejected kid → the same opaque `None`; no kid/DSN/token echoed.
   (FR-006)

## Manual gate checks (autopilot)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_public_safety`, `test_no_execution_path_outside_the_gateway`) + the
events serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the existing 056 auth/security suite. NOTE: the
new tests must NOT make a real network call (supply a fake `_fetch_jwks`); run the full pytest + any
verify Workflow at DIFFERENT times; scan new test files for forbidden tokens (no `secret = "..."`;
benign placeholders) before committing.
