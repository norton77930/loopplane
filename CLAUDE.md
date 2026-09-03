<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/086-cluster-fair-turn/plan.md
<!-- SPECKIT END -->

# LoopPlane Claude Instructions

## Shared Rules

- Follow the non-SPECKIT sections of `AGENTS.md` and `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`. Rules live there; this file holds pointers only, so it cannot drift.

## SPECKIT Block Caveat

- The agent-context tooling (`.specify/extensions/agent-context/agent-context-config.yml`) manages only `AGENTS.md`. The SPECKIT block above is a manual mirror; whenever the `AGENTS.md` block is regenerated, update this one in the same change. On divergence, the `AGENTS.md` block wins.

## Claude Code Plan Mode

- Run read-only audits and research in plan mode without modifying files.
- Use ExitPlanMode only for plans that will write code or files.
- Plan files live outside the repo and are never committed.

## Source of Truth

- Same trust ladder as `AGENTS.md` ("Architecture Source of Truth"); completion status comes from `docs/loopplane-agent-board.md` only.
