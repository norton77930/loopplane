<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/086-cluster-fair-turn/plan.md
<!-- SPECKIT END -->

# LoopPlane Codex Instructions

## Spec Kit Ownership

- The `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` section is managed by Spec Kit. Do not edit that block manually; refresh it through Spec Kit integration or agent-context commands.
- This repository intentionally keeps both Claude and Codex integrations. Do not remove `.claude/`, `CLAUDE.md`, `.agents/`, or `AGENTS.md` as cleanup.
- Codex is the default Spec Kit integration. Use the repo-local Codex skills in `.agents/skills` and the `$speckit-*` invocation style.

## LoopPlane Autopilot

- Use `.agents/skills/loopplane-roadmap-autopilot` only when the user explicitly asks for LoopPlane autopilot, `/loop`, `/loop auto`, `/loop 1m`, or equivalent roadmap automation.
- Outside explicit autopilot mode, do not commit or push unless the user asks.
- In explicit autopilot mode, follow `docs/loopplane-agent-board.md` as the control document, use Spec Kit flow order, validate before each commit, and push only safe scoped commits.
- Never modify or commit raw `openspec/`, private paths, internal names, credentials, tokens, or secrets.

## Architecture Source of Truth

- Trust ladder: `src` + `tests` + `pyproject.toml` > `docs/loopplane-agent-board.md` (the only completion authority) > `docs/api-reference.md` > `specs/` > `docs/capabilities.md`/`docs/gap-analysis.md` > `CHANGELOG.md` > `README.md`.
- Never infer completion from spec `Status:` fields or unchecked boxes in older units' tasks.md — see `docs/architecture/SPEC_KIT_ALIGNMENT_RULES.md`.
- Audit snapshot and full map: `docs/architecture/ARCHITECTURE_AUDIT.md`.

## Load-Bearing Files

- Highest blast radius: `src/loopplane/model/`, `src/loopplane/errors.py`, `src/loopplane/events/`, `src/loopplane/context.py`, `src/loopplane/gateway/`, `src/loopplane/host/assembly.py`.
- Before editing any of them, grep inbound imports and read the owning block in `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`.

## Human Approval Gates

- Stop and ask before: event/checkpoint schema changes, gateway SPI or stage-order changes, any default-value change, new dependencies or extras, outward web/API contract changes, and releases.
- Full list: `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §E.

## Forbidden Actions

- Never: touch or commit `openspec/`, hand-edit SPECKIT managed blocks, run destructive git (`reset --hard`, force push) or blind bulk `git add`, convert lazy/TYPE_CHECKING imports to top-level, or retro-edit Verified specs/tasks.
- Full list: `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` §F.
