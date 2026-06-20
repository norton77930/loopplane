# Feature Specification: Worktree Isolation

**Feature Branch**: `051-worktree-isolation`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Isolated git worktrees for agent work: agent-facing tools to create, list, and remove managed git worktrees so an agent can make changes in an isolated checkout that does not disturb the main working tree, bounded and governed. Unit 051, Tier-2 (autonomy & workflow); closes gap G8 (claude-code Enter/ExitWorktree). Additive; reuse the working-scope + run_command; no new dependency."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent works in an isolated worktree (Priority: P1)

While working in a git repository, the agent creates an **isolated git worktree** (a separate
checkout, optionally on a new branch), does its file edits / commands there, and the **main
working tree is left untouched** — so risky or exploratory changes are contained and can be
reviewed or discarded without disturbing the primary checkout.

**Why this priority**: This is gap G8 and the unit's core value — the reference harness lets an
agent enter an isolated worktree for changes; LoopPlane confines tools to one working scope with
no isolation primitive. A worktree lets an agent make contained, reviewable changes.

**Independent Test**: In a throwaway git repo (a test fixture), the agent creates a worktree;
edits/commands run against the worktree path; the main working tree shows no change; the worktree
holds the change.

**Acceptance Scenarios**:

1. **Given** the working scope is a git repository, **When** the agent creates a worktree (with
   an optional branch name), **Then** it receives the worktree's id + path and the worktree exists
   as an isolated checkout, with the main working tree unchanged.
2. **Given** an isolated worktree, **When** the agent makes a change inside it, **Then** the change
   is confined to the worktree (the main tree is unaffected).

---

### User Story 2 - Inspect and remove worktrees (Priority: P2)

The agent can list the run's managed worktrees and remove one it no longer needs (cleaning up the
checkout), so isolated work does not accumulate.

**Why this priority**: Isolation is only safe/useful if worktrees can be enumerated and removed.

**Independent Test**: Create a worktree; `list` includes it (id + path); `remove` deletes it (the
worktree directory is gone, the git metadata pruned); an unknown id yields a clear error.

**Acceptance Scenarios**:

1. **Given** worktrees exist, **When** the agent lists them, **Then** it sees each worktree's id +
   path + branch (metadata only).
2. **Given** a managed worktree, **When** the agent removes it, **Then** the checkout is deleted +
   pruned and it no longer appears in the list.

---

### User Story 3 - Bounded, governed, contained, lifecycle-bound (Priority: P3)

Worktrees are bounded (a per-run cap), governed (Gateway tools; created only inside a managed area
of the working scope — never escaping it), contained (a git failure / non-repo / bad input is a
normalized error, never a crash), default-off (byte-identical when disabled), and lifecycle-bound
(managed worktrees are cleaned up at the run/session scope exit; nothing leaks on disk).

**Why this priority**: Filesystem + git side effects are high-risk — worktrees escaping the
working scope, unbounded accumulation, or a git error crashing the run are unacceptable (the
project's working-scope confinement + the 048–050 safety posture).

**Independent Test**: Exceeding the worktree cap is denied; creating a worktree in a non-git or
out-of-scope path is a normalized error; with the feature disabled no worktree tools are offered;
managed worktrees are removed at scope exit.

**Acceptance Scenarios**:

1. **Given** the worktree cap is reached, **When** the agent creates another, **Then** it is
   denied with a normalized error and no worktree is created.
2. **Given** managed worktrees exist at run end, **When** the scope exits, **Then** they are
   cleaned up (directories removed + git metadata pruned); nothing leaks.

---

### Edge Cases

- **working scope is not a git repo**: a clear normalized error (no crash).
- **remove/inspect an unknown worktree id**: a clear normalized error.
- **a worktree path that would escape the working scope**: rejected (confinement preserved).
- **git not available / a git command fails**: a normalized, public-safe error (no traceback).
- **feature disabled / cap 0**: no worktree tools registered (byte-identical).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide agent-facing tools, reachable only through the Tool Gateway
  (V), to **create** a managed git worktree (an isolated checkout, with an optional branch),
  **list** the run's managed worktrees, and **remove** one.
- **FR-002**: A created worktree MUST be an isolated checkout such that changes made inside it do
  **not** affect the main working tree.
- **FR-003**: Worktrees MUST be created only inside a **managed area of the working scope** and
  MUST NOT escape the working-scope confinement (the existing 001/002 invariant); a path that
  would escape MUST be a normalized error.
- **FR-004**: `list` MUST report each managed worktree's id + path + branch as metadata only;
  `remove` MUST delete the checkout + prune its git metadata; an unknown id MUST be a clear
  normalized error.
- **FR-005**: Worktrees MUST be **bounded** — a configurable per-run maximum; exceeding it MUST be
  denied with a normalized error and no worktree created.
- **FR-006**: Failures (non-git working scope, git unavailable, a failing git command, bad input)
  MUST be **contained** — a normalized, public-safe error; they MUST NOT raise across the Gateway
  or crash the run.
- **FR-007**: Managed worktrees MUST be **lifecycle-bound** — cleaned up (directories removed + git
  metadata pruned) at the run/session scope exit; nothing leaks on disk.
- **FR-008**: The feature MUST be **opt-in and default-off** (byte-identical when disabled), with
  no worktree tools registered and no event-schema / content-model change when off.
- **FR-009**: The capability MUST reuse existing seams — git operations via the existing
  shell-execution path (`run_command`-style), the working-scope confinement, and the per-run
  manager + neutral-Protocol threading pattern (048/049/050) so the controller/loop never import
  the tools layer; no new runtime dependency.

### Key Entities *(include if feature involves data)*

- **Worktree (managed)**: an isolated git checkout created by the agent under a managed area of the
  working scope, identified by a worktree id, with a path + branch + status.
- **Worktree manager / registry**: the per-run collection of managed worktrees, surfaced by
  `list` and cleaned up at scope exit.
- **Managed area**: a subdirectory of the working scope where managed worktrees live (so they stay
  within the working-scope confinement).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the feature enabled (a test git repo), creating a worktree yields an isolated
  checkout; a change inside it leaves the main working tree unmodified in 100% of covered
  scenarios.
- **SC-002**: list/remove reflect a worktree's real lifecycle (present → removed/pruned); an
  unknown id and an out-of-scope/non-git path each error cleanly.
- **SC-003**: The worktree cap denies excess; a git/IO failure never crashes the run; managed
  worktrees are cleaned up at run/session end (nothing leaks on disk).
- **SC-004**: With the feature disabled, behavior is byte-identical to today — the existing test
  suite passes unchanged and no event-schema / content-model change is introduced.

## Assumptions

- Worktree operations reuse the existing shell-execution path (`git worktree add/list/remove`)
  within the working scope; no new library dependency. Tests use a throwaway git repo fixture (no
  network).
- Managed worktrees live under a managed subdirectory of the working scope (e.g. a dot-prefixed
  directory) so they never escape the working-scope confinement (FR-003) — the exact location +
  the agent-tools-vs-host-managed shape are confirmed at the plan boundary review (expected to be
  additive + default-off, the 048/049/050 pattern; no new ADR unless the plan finds a confinement
  / contract conflict, in which case the maintainer is consulted).
- Out of scope: automatic merge/PR of worktree changes back to the main branch, cross-session /
  persistent worktrees, and any worktree UI.
- Default-off; bounded; contained; Gateway-only (V); working-scope-confined (001/002);
  public-safe (VII). Per Constitution IX the concept is borrowed from the reference harness but
  re-derived; III keeps it a bounded, opt-in autonomy primitive.
