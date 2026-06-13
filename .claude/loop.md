# LoopPlane — Roadmap Autopilot (`/loop`)

You are running **LoopPlane Roadmap Autopilot**. Drive the roadmap autonomously; do not wait for
the user to prompt each Spec Kit step.

## On every `/loop` run

1. **Read `docs/loopplane-agent-board.md` first.** It is the authoritative control document
   (roadmap 000–014, active feature, Spec Kit flow, validation, commit/push policy, stop
   conditions, Dynamic Workflow policy).
2. **Run Roadmap Autopilot.** Determine the current incomplete step from **repository state**:
   the current branch, `.specify/feature.json`, and the `specs/` feature directories
   (use the decision algorithm in board §6).
3. **Continue the Spec Kit flow** for the active unit, executing the next incomplete step
   (autopilot may chain steps), in this order:
   `specify → clarify/checklist (if needed) → plan → tasks → analyze → implement → final review`.
   - Honor the allowed-changes scope per board §5. **No implementation code before `implement`.**
   - During `implement`, only create/modify Python source that `tasks.md` requires — nothing
     speculative.
4. **Validate before committing** (board §10): `git diff --check`, the `openspec/` scan, the
   public-safety scan, and `pytest` (green before any commit touching source/tests).
5. **Commit and push** safe, scoped changes (board §11 messages). One commit per stable step;
   **push after each safe commit**.
6. **Advance to the next roadmap unit only when the current unit is `Verified`** (board §3/§7),
   and update the board status before moving on.
7. **Dynamic Workflow is an accelerator only.** Use it during `analyze` / `implement` for audits,
   cross-artifact consistency checks, coverage sweeps, public-safety scans, and large independent
   task groups. It is **not** the roadmap controller — never use it for branch creation, merge,
   feature transition, or destructive ops. Final integration and the test run happen in the main
   session.
8. **Stop only on hard stop conditions** (board §9). Otherwise keep going.

## Never

- Modify or commit raw `openspec/`.
- Copy legacy/private implementation code.
- Commit private paths, internal names, IPs, keys, tokens, or secrets.
- Perform destructive git operations, or rewrite 001/002 public contracts without approval.

## Report after each step

completed step · files changed · tests run · validation result · commits created · next step.
