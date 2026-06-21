---
name: "loopplane-roadmap-autopilot"
description: "Run LoopPlane roadmap autopilot when the user asks for /loop, /loop auto, /loop 1m, or autonomous Spec Kit roadmap execution in this repository."
compatibility: "Requires the LoopPlane repository, Spec Kit project structure, and Codex Spec Kit skills in .agents/skills."
metadata:
  author: "loopplane"
  source: ".claude/loop.md"
---

# LoopPlane Roadmap Autopilot

Use this skill only when the user explicitly asks for LoopPlane autopilot,
`/loop`, `/loop auto`, `/loop 1m`, or autonomous Spec Kit roadmap execution.
Do not treat ordinary coding requests as autopilot.

## Control Document

At the start of every run, read `docs/loopplane-agent-board.md`. It is the
authoritative control document for:

- active roadmap unit
- active feature directory
- current Spec Kit step
- allowed changes
- validation commands
- commit and push policy
- stop conditions

Also inspect `.specify/feature.json`, the active `specs/<feature>/` directory,
and current git state before choosing the next step.

## Command Mapping

The board may mention Claude-style `/speckit.*` commands. In Codex, use the
repo-local skills in `.agents/skills`:

- `/speckit.specify` -> `$speckit-specify`
- `/speckit.clarify` -> `$speckit-clarify`
- `/speckit.checklist` -> `$speckit-checklist`
- `/speckit.plan` -> `$speckit-plan`
- `/speckit.tasks` -> `$speckit-tasks`
- `/speckit.analyze` -> `$speckit-analyze`
- `/speckit.implement` -> `$speckit-implement`

Before executing one of these phases, load and follow the corresponding
`SKILL.md` instructions. Do not hand-roll Spec Kit behavior when a matching
Spec Kit skill exists.

## Execution Rules

Follow the Spec Kit flow:

```text
specify -> clarify/checklist -> plan -> tasks -> analyze -> implement -> final review
```

- Determine the next incomplete step from repository state.
- Execute only the next incomplete step unless the user explicitly requested
  autopilot mode with `/loop auto`, `/loop 1m`, or equivalent wording.
- Do not implement during specify, clarify, checklist, plan, tasks, or analyze.
- During implement, modify only files required by the active `tasks.md`.
- Keep implementation serial unless the board explicitly allows parallel
  analysis or audits.
- Stop on any hard stop condition listed in the board.

## Safety Rules

- Do not create, switch, or merge branches for autopilot; the board defines the
  branch strategy.
- Do not perform destructive git operations.
- Do not modify or commit raw `openspec/`.
- Do not copy private or legacy implementation code.
- Do not commit private paths, internal names, IP addresses, credentials,
  tokens, keys, or secrets.
- Do not rewrite public contracts from earlier phases unless the board and the
  user explicitly authorize it.

## Validation and Git

Before any commit, run the validation commands required by
`docs/loopplane-agent-board.md`, including at minimum:

- `git diff --check`
- `git diff --name-only | Select-String "^openspec/"`
- the public-safety scan described by the board
- the test command required for the current change scope

If validation fails, fix once when the repair is obvious. If it still fails or
the cause is not obvious, stop and report the blocker.

In explicit autopilot mode, commit only safe scoped changes after validation
passes, then push. Outside explicit autopilot mode, do not commit or push unless
the user asks.

## Report Format

After each step, report:

1. completed step
2. files changed
3. tests run
4. validation result
5. commits created
6. next recommended step
