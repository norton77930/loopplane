# Contract: webapi Route-Snapshot Invariance (US6a)

Normative contract for `tests/contract/test_webapi_route_snapshot.py` and the router split of `src/loopplane/webapi/app.py`.

## Purpose

Make "the outward HTTP/SSE/WS contract did not change" a test outcome rather than a review claim, so the US6a refactor provably does **not** trigger the §E gate for outward web/API contract changes.

## Capture (before any re-filing)

- Build the app via the public `create_app(...)` with a representative configuration (default-deny auth acceptable; no network).
- Record the sorted route inventory per [data-model.md](../data-model.md) §2: `(methods, path, endpoint __name__, response_model class name, status_code)`. Fields are refactor-neutral: moving an endpoint function to another module must not change any of them.
- Record the canonicalized `app.openapi()` JSON (sorted keys, stable separators). The OpenAPI document is the outward contract; byte-equality of its canonical form is the strongest §E non-trigger proof.
- Both expectations are checked in with the capture commit, BEFORE the split lands.

## Invariance requirement

After the split (routers under `src/loopplane/webapi/routers/`, mounted by `create_app()`):

1. The route inventory compares equal.
2. The canonical OpenAPI JSON compares equal.
3. `create_app(...)` keyword surface is unchanged (assert via `inspect.signature`).
4. `tests/contract/test_webapi_boundary.py` and the full §G suite still pass.

Any diff = the refactor failed its own requirement; fix the refactor, never the snapshot. Legitimate future contract changes (outside this unit) update the snapshot **together with** the §E approval record.

## Scope guard

The split touches only `src/loopplane/webapi/**`. No import-boundary change: routers live inside `webapi`, so `test_webapi_boundary.py`'s allow-list (`events`, `host`, `webapi`, `commands`) still holds. `capability_manager.py` (US6b) is explicitly out of this contract and blocked on 078 Verified.
