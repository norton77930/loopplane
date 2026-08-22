# Quickstart: MCP Interactive OAuth

Written against the design in [plan.md](plan.md) and [contracts/](contracts/mcp-interactive-oauth.md).
Nothing below exists yet — this unit is gated on ADR 0019 acceptance.

## For an embedder

Two things to supply, both host responsibilities by decision (ADR 0019 D1):

1. **An authorization handler** — present the URL somewhere a person can see it, and return what the
   redirect delivered. How is entirely yours: open a browser, print the URL, push it into your own UI.
2. **A token store** — optional. Without one, material lives for the process lifetime and a restart
   requires authorizing again. With one, you decide where it lives and how it is protected;
   `src/loopplane` writes nothing to disk under any configuration.

Then declare the mode on the server configuration. It is mutually exclusive with the 059
`auth_token`, and valid on `http` and `sse` only.

Nothing changes for a configuration that does not use it. A server with no mode declared behaves
exactly as it does today.

## For a Desktop user

Add the server in the MCP settings panel, choose interactive authorization, and connect. The app
opens your browser; you approve; the tools appear. Closing and reopening the app does not ask again.

Disconnecting discards the stored authorization; reconnecting asks again.

The settings panel shows one of three states — authorized, needs authorization, failed — and never
shows a credential. Nothing credential-shaped reaches the app's logs, diagnostics, or a profile
backup archive: the material is encrypted by the OS keystore and stored outside the profile root, so
a backup cannot contain it by construction.

## In CI, a container, or any headless process

A server declaring interactive authorization will **not connect**, and will not attempt a connection
without a credential. That is deliberate: silently connecting unauthenticated, or silently reaching
for a static token, would turn a missing credential into a misconfiguration nobody notices.

Other servers are unaffected — the failure is contained to the one that needs authorizing.

**Already-authorized servers keep working.** Renewal never needs a browser, so scheduled and
long-running work does not stall as tokens expire. Only the first authorization needs a person.

## What has not changed

- The 059 static-token path, untouched.
- `websocket`, still without transport auth (an SDK limitation recorded in ADR 0007 D3).
- The Web surface, unchanged — ADR 0016's divergence stands.
- What the model sees: authorization is never a tool, never a tool argument, never a content block.
