# Contract: 077 Delivery Convergence

## Frozen history and ownership

- Do not edit completed `spec.md`, `plan.md`, or `tasks.md` artifacts for units 076, 080, or 081.
- Keep a complete working-tree inventory separate from the narrower 077 delivery candidate set.
- Classify every candidate file and mixed hunk as prior-unit, 077, or local/unknown.
- Exclude `.superpowers/**`, raw `openspec/**`, ignored browser/QA evidence, local logs/PIDs, and unclassified user files.
- An inventory entry is never staging authorization.

## Human gate

Before implementation begins, record explicit maintainer approval or rejection of:

1. `GET /v1/sessions/{session_id}/agent-controls`, including authoritative non-durable active/last-accepted posture and projected actions;
2. the optional per-run `permission_mode` input across applicable HTTP/live submission contracts;
3. the exact bounded non-image upload handoff and stale/`read_upload`-unavailable pre-model rejection semantics; and
4. regeneration of backend-owned shared Web type artifacts for those additions.

If approval is not granted, 077 remains at the specification gate and implementation tasks stay blocked.

A separate ADR plus approval is required if implementation discovers any need for durable browser-mutated plan/permission/budget state, changed enforcement/approval ordering, a new artifact persistence/sharing boundary, an event/checkpoint/Gateway contract change, a dependency/default change, or a loosened architecture boundary.

## Required fresh evidence

- Focused Python unit/contract/integration tests for projection safety, per-run mode selection, deny-wins, plan exit, budget states, ownership, references, and defaults.
- Repository-wide Ruff format/check, strict mypy, full pytest with literal failures/skips, and package build.
- Web dependency sync, typecheck, focused/full Vitest, generated-type drift checks, and production build.
- Desktop dependency sync compatible with the environment, typecheck, and full tests.
- Standalone Chromium matrix for 1440/1024/768/375 plus 640/320 reflow; en/zh-TW; light/dark; keyboard/focus; reduced motion; forced colors; no document overflow.
- Two-principal non-disclosure matrix over projection, selection, cost, context, and references.
- Diff whitespace, architecture boundary, Spec Kit alignment, raw-openspec exclusion, and public-safety scans including untracked candidates.

Historical counts from prior units are not 077 evidence.

## Documentation/status convergence

Only after implementation and every required gate pass:

- update public API documentation for approved host/Web contract additions;
- update relevant Web-host/capability documentation and `[Unreleased]` records required by repository rules;
- append literal validation and known limitations to 077 `quickstart.md`;
- run post-write consistency/public-safety checks;
- transactionally update the agent board and active pointer only when task completion, evidence, and docs agree.

Any failed post-write check restores the prior in-progress board/pointer/task state.

## Publication boundary

Specification completion does not authorize staging, commit, branch, push, pull request, tag, version, release, or deployment.
