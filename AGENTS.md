<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/075-web-capability-management/plan.md
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
