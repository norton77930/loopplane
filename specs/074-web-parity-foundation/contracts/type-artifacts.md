# Contract: Type Artifacts

## Purpose

Keep web-facing TypeScript types aligned with backend-owned API and session-event contracts.

## Source Of Truth

Backend-owned schemas or fixtures define the public web contract for:

- live ticket request/response;
- live client and server envelopes;
- extended session summaries;
- star, fork, search, and bulk-delete payloads;
- representative normalized session events consumed by the web UI.

The web app may generate TypeScript types, validate handwritten wrappers, or use a hybrid approach, but the check must be repeatable in CI.

## Drift Detection

Validation must fail clearly when:

- a backend field required by the web client is renamed or removed;
- a required event payload shape changes without updating the artifact workflow;
- a new user-visible event used by the UI has no fixture/schema coverage;
- generated or validated output is stale.

At least one representative API response and one representative session event drift case must be covered by tests.

## Artifact Rules

- Artifacts must be deterministic.
- Artifacts must not include credentials, tokens, private paths, hostnames, or raw reference material.
- Artifact generation or validation must not require network access.
- Existing REST/SSE TypeScript clients remain compatible.

## Expected Commands

The implementation phase may add a focused command or test target for type validation. It must also keep these existing gates green:

- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run build`
- backend contract tests under `uv run pytest`
