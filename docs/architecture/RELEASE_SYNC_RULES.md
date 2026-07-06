# Release & Documentation Sync Rules

> Defines when each status/release artifact must be synchronized. Roles: the board = per-unit completion authority (live); CHANGELOG = release record; `__version__` = the released version (hatch reads it from `src/loopplane/__init__.py`; see pyproject `[tool.hatch.version]`).

## Sync matrix

| Event | Must sync | Notes |
|---|---|---|
| Unit starts (`speckit-plan`) | The `AGENTS.md` + `CLAUDE.md` SPECKIT blocks | `AGENTS.md` via `speckit-agent-context-update` (the tooling manages only `AGENTS.md`); mirror the block into `CLAUDE.md` manually in the same change — on divergence, `AGENTS.md` wins |
| ADR approved | New `docs/adr/NNNN-*.md`; referenced from the unit's plan.md | ADRs are approved at the plan stage, before implementation |
| Unit Verified | `docs/loopplane-agent-board.md` (required); a `CHANGELOG.md` **[Unreleased]** entry (required — new rule); `docs/api-reference.md` (required if the public surface changed) | The [Unreleased] rule prevents another 064–075-style twelve-unit backlog |
| Release | Bump `__version__`; promote [Unreleased] → `[X.Y.Z] – date`; git tag; bring `docs/capabilities.md` + `docs/gap-analysis.md` up to the released line; recalibrate the README's high-level claims | The CHANGELOG section references the ADRs it ships |
| Outward contract change (HTTP/SSE/WS/event/record schema) | `docs/api-reference.md` in the same unit; the apps' generated types | Human approval gate |
| Positioning/installation change | README + `docs/getting-started.md` together (their install sections are currently word-identical) | Prevents the two files diverging |

## Per-artifact rules

- **`src/loopplane/__init__.py` `__version__`**: bumped only in the release commit; MUST equal the newest CHANGELOG version section.
- **`CHANGELOG.md`**: Keep a Changelog + SemVer; a unit enters [Unreleased] when Verified (precedent: unit 042 went through [Unreleased] and was promoted at release).
- **`docs/loopplane-agent-board.md`**: unit status maintained live; the single completion authority; releases do not change its semantics.
- **`docs/adr/`**: one decision per file, ascending numbers; referenced by the CHANGELOG at release time.
- **`docs/api-reference.md`**: updated in the same unit as the public-surface change (part of the unit's definition of done).
- **`docs/capabilities.md` / `docs/gap-analysis.md`**: brought up to the released line no later than the release; their "deferred / still open" lists are re-audited at every release (the audit found several already falsified).
- **`README.md`**: tied to release boundaries only; never enumerates per-unit features.
- **`specs/*`**: frozen after Verified (rules in `SPEC_KIT_ALIGNMENT_RULES.md` §2/§4).

## Version semantics (proposed; maintainer decides)

MINOR = a batch of new-capability units; PATCH = remediation/fixes; MAJOR reserved for contract breaks.

## Outstanding sync debt (as of the 2026-07-06 audit) and pay-down order

1. `CHANGELOG.md`: add [Unreleased] (or directly [0.5.0]) covering units 064–075 + ADRs 0011–0014 — version number/timing is a maintainer decision.
2. Update `docs/capabilities.md` and `docs/gap-analysis.md` through unit 075.
3. ~~`CLAUDE.md` SPECKIT pointer 067 → 075~~ — done 2026-07-06 (manual mirror; the tooling does not cover `CLAUDE.md`, see the sync matrix).
4. Rewrite the README per its outline (depends on step 2).
5. At release: bump `__version__` + tag.
