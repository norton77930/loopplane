# Quickstart / Validation: Web Interaction Resilience & States (032)

See [contracts/interaction-resilience.md](./contracts/interaction-resilience.md).

## Automated gate (frontend-only)

```sh
npm --prefix apps/web run typecheck
npm --prefix apps/web test     # focus-trap + Esc + option nav; error Retry; toast; skeleton; empty-state prompt
npm --prefix apps/web run build
```

Expected: all green; the **Python suite and backend are unchanged** (no backend edit).

## Manual QA (browser)

```sh
uv run uvicorn serve_web_demo:app --host 127.0.0.1 --port 8000
npm --prefix apps/web run dev    # token: dev-token
```

- Trigger an approval/question → focus is trapped in the dialog; **Tab** cycles within; **Esc**
  dismisses with the safe default (deny/cancel); focus returns to where it was.
- Force a disconnect → the banner offers **Retry**; clicking it re-establishes the stream.
- A transient action (copy / rename) → a brief **toast** appears and auto-dismisses.
- While sessions/history load → **skeletons** show; an empty conversation shows **example prompts**
  that start a chat when clicked.

## Rollback

Revert the `apps/web` diff (the new `Modal`/`Toast`/`Skeleton` + `useFocusTrap`, the dialog/banner/
list edits) → unit 031. No backend or Python change to undo.
