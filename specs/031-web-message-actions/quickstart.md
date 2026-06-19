# Quickstart / Validation: Web Message Actions (031)

See [contracts/message-actions.md](./contracts/message-actions.md).

## Automated gate (frontend-only)

```sh
npm --prefix apps/web run typecheck
npm --prefix apps/web test     # clipboard helper, message copy, regenerate, code-block copy
npm --prefix apps/web run build
```

Expected: all green; the **Python suite and backend are unchanged** (no backend edit).

## Manual QA (browser)

```sh
uv run uvicorn serve_web_demo:app --host 127.0.0.1 --port 8000
npm --prefix apps/web run dev    # token: dev-token
```

- Hover a message → **Copy** places its text on the clipboard (brief confirmation).
- After a completed turn → **Regenerate** re-sends the last user prompt; it is disabled while a
  run is in flight and absent when no user turn has been sent.
- An assistant code block shows a **copy button** that copies the exact code.

## Rollback

Revert the `apps/web` diff (the `lib/clipboard.ts` helper, the `MessageList`/`Markdown`/`App`
edits) → unit 030. No backend or Python change to undo.
