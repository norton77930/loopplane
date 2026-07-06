# Spec Kit Alignment Rules

> Decides which Spec Kit / documentation artifact a given change must touch. For workflow order, see `.specify/memory/constitution.md` (Development Workflow & Quality Gates).

## 1. When to add a new spec (open a new unit)

Any of the following → new unit (add a board row, take the next free number):

- A user-visible new capability, a new package, a new extra, or a new outward contract (HTTP/SSE/WS/event/record schema).
- A change that needs an ADR-level decision (precedents: units 048–063, 068–072).
- A default-behavior change (breaking byte-identity).
- Out-of-scope changes to an already **Verified** unit — always open a new unit; never retro-edit the old one.
- Batched quality remediation → a remediation unit (precedent: `specs/073-code-review-remediation`).

No spec needed: a single bug fix that changes no contract (ship with a test, record under CHANGELOG `[Unreleased]`). Cross-boundary or batched fixes → a remediation unit.

## 2. When to update an existing spec.md

Only for **in-flight (not yet Verified)** units: requirement clarification (`speckit-clarify`), acceptance-criteria fixes.
After Verified, a spec is historical record and MUST NOT be retro-edited; corrections go in as appended errata notes that do not alter the original meaning.

## 3. When to update plan.md

Only for design changes to an in-flight unit; every update MUST re-pass the Constitution Check gate (built into `speckit-plan`). Where an ADR is needed, propose it at the plan stage and obtain maintainer approval before implementing.

## 4. When to update tasks.md

- Only in-flight units may check/add/remove tasks.
- After Verified, tasks.md is frozen.
- If you find checkbox drift in an older unit: **do not backfill**. The only legitimate path is updating `docs/spec-task-audit-exceptions.md` in the same change and confirming `tests/contract/test_spec_task_audit.py` stays green.

## 5. When to update README.md

Only at release boundaries or when positioning/installation changes (rules in `RELEASE_SYNC_RULES.md`). The README MUST NOT enumerate per-unit features (that is how it froze once already).

## 6. When to update docs/api-reference.md

Any public symbol, endpoint, or event/record schema change — updated **within the same unit**; this is part of the unit's definition of done.

## 7. When to update AGENTS.md / CLAUDE.md

- The `<!-- SPECKIT START/END -->` block in `AGENTS.md` is tool-managed: MUST NOT be hand-edited; it is regenerated via `speckit-agent-context-update` whenever a new unit starts (the tooling's `context_file` is `AGENTS.md` — see `.specify/extensions/agent-context/agent-context-config.yml`).
- The identical block in `CLAUDE.md` is **not** covered by that tooling (which is how it once lagged eight units). Until the maintainer extends the config, keep it as a manual mirror of the `AGENTS.md` block, updated in the same change; on divergence, `AGENTS.md` wins.
- Outside the managed block: keep rules as pointers into `docs/architecture/*`; never copy rule text (single source, no drift).

## 8. When the README is stale: how an AI agent determines the real state

Work down the trust ladder; MUST NOT conclude a feature is absent just because the README omits it:

1. Check the unit's row in `docs/loopplane-agent-board.md`.
2. Check whether the symbols exist in `src/loopplane/**` (grep / `__all__`).
3. Check whether the matching tests exist (`tests/unit|contract|integration`).
4. Only then consult `docs/api-reference.md` → `specs/<unit>` → capabilities/gap-analysis → CHANGELOG.

Treat the README as legacy positioning material only.

## 9. When old tasks checkboxes conflict with the board

- **The board wins** (`docs/loopplane-agent-board.md` is the single completion authority).
- Check whether the unit is already listed in `docs/spec-task-audit-exceptions.md`: listed → reconciled, ignore the checkboxes; not listed (new drift) → **stop and report to a human**; do not change either side yourself.

## 10. The spec `Status:` field

Currently every spec still says `Draft` and the field is unmaintained. Until the maintainer decides (backfill vs. formally deprecate the field), MUST NOT infer completion from `Status:` and do not backfill it on your own.
