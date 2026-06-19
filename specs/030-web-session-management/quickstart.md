# Quickstart / Validation: Web Session Management (030)

See [contracts/session-management.md](./contracts/session-management.md) and
[data-model.md](./data-model.md) for shapes.

## Automated gates

```sh
# Backend
uv run pytest        # incl. new checkpoint (both backends) + host/controller + webapi session-mgmt tests
uv run ruff check .
uv run mypy          # strict

# Frontend
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected: all green; the **webapi import-boundary test stays green**; the Python suite has the new
session-management tests (including the **non-owner 404** cases).

## Targeted backend checks

- **Title last-wins (both backends)**: open a session, `set_title("A")`, `set_title("B")` →
  `list_sessions()` and a resume both report `label == "B"`.
- **Delete (both backends)**: `delete_session(id)` removes it from `list_sessions()`/`load()`;
  calling it again on the same id is a no-op (idempotent).
- **Non-owner 404**: with two principals, principal B's `PATCH`/`DELETE` of principal A's session
  each return **404** `{"detail": ...}`; A's session is unchanged.

## Manual QA (browser)

Bind the demo backend to `127.0.0.1` (Windows dual-stack note) and run the dev server:

```sh
uv run uvicorn serve_web_demo:app --host 127.0.0.1 --port 8000
npm --prefix apps/web run dev    # open the printed URL; token: dev-token
```

Check:

- The sidebar lists sessions by **title** (not the raw id), grouped **Today / Yesterday / Earlier**.
- **Rename** a session → the new title shows immediately; **reload** the page and **restart** the
  backend → the title is still there.
- **Delete** a session (confirm the prompt) → it disappears; reload/restart → it stays gone;
  deleting the **open** session returns the app to an empty/new state.
- An **untitled** session shows a graceful fallback (never the raw id alone / never blank).

## Rollback

Revert the `030` diff: drop `set_title`/`delete_session` from the store + controller + host, the two
webapi routes, and the `SessionSummaryView` field additions; restore the pinned `{session_id,
label}` assertions. Already-saved titles become inert; deleted sessions stay deleted.
