# Contract: Session Management

## Purpose

Extend web session management with modern agent-app affordances while preserving existing session APIs and principal scoping.

## Session Summary

Existing summary fields remain valid. New fields are additive and optional for older clients:

- `model`: model id associated with the session.
- `starred`: persisted boolean flag.
- `forked_from_session_id`: source session id for forks.
- `forked_from_sequence`: selected source point for forks.
- `search_snippet`: contextual search result text when returned by search.

All summaries must belong to the authenticated principal.

## Draft Chat And Model Preference

- Browser may hold a local draft before any persisted session exists.
- Preferred model may be stored locally for future draft chats.
- First submit creates the backend session and sends the selected model when still available.
- No provider API key or provider secret is collected in browser UI.

## Star And Unstar

- Users may star or unstar only owned sessions.
- Star state survives refresh and page reload.
- Non-owned session ids return the same non-disclosing failure behavior used by existing owner-scoped APIs.

## Fork

- Users may fork only owned sessions.
- A fork creates a new owned session from a selected conversation point.
- The source session remains unchanged.
- Fork metadata is visible in the new session summary.

## Search

- Search returns only owned sessions.
- Matching may use title and retained conversation text available to the existing history/checkpoint layer.
- Results are stable enough for selection and may include a snippet.

## Bulk Delete

- Request must include a non-empty `session_ids` list and explicit confirmation.
- Only owned sessions are removed.
- Already-deleted ids are handled deterministically.
- If the active session is deleted, the UI selects a remaining session or new-chat state using a deterministic fallback.

## Compatibility

- Existing rename, delete, list, history, and title behavior remains compatible.
- Missing additive fields must not break older clients.
