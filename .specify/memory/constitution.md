<!--
Sync Impact Report
==================
- Version change: (uninitialized template) → 1.0.0
- Modified principles: initial adoption — all template placeholders replaced
  with ten concrete principles (I–X listed below)
- Added sections:
  - Reference Material & Confidentiality Constraints
  - Development Workflow & Quality Gates
- Removed sections: none (template placeholder sections materialized)
- Templates:
  - .specify/templates/plan-template.md ✅ aligned (Constitution Check gates
    are derived from this file at /speckit-plan time; no edit required)
  - .specify/templates/spec-template.md ✅ aligned (no constitution-specific
    sections required; no edit)
  - .specify/templates/tasks-template.md ✅ updated (test tasks are now
    REQUIRED per Principle X — Testable Evolution)
  - .specify/templates/checklist-template.md ✅ aligned (no edit)
- Follow-up TODOs: none
-->

# LoopPlane Constitution

## Core Principles

### I. Spec-First Development

All implementation MUST trace back to an approved artifact: a spec, a plan,
a task list, or an ADR. No implementation work may begin before the
corresponding spec, plan, and tasks have been written and reviewed.

- Every code change MUST reference the spec/plan/task/ADR that motivates it.
- Changes with no traceable artifact MUST be rejected in review.
- Exploratory spikes are allowed only in throwaway branches and MUST NOT be
  merged; their findings feed back into specs or ADRs instead.

**Rationale**: LoopPlane is itself a spec-first control plane; its own
development process must demonstrate the discipline it exists to enforce.

### II. Greenfield Implementation

This repository starts clean. Old code and the local OpenSpec material are
references only.

- Implementation code MUST be written fresh for this repository.
- Copying old implementation code is prohibited by default; any exception
  MUST be justified in an ADR and reviewed for public-safety (Principle VII).
- Legacy designs may inform new specs, but the spec — not the legacy code —
  is the source of truth.

**Rationale**: A clean start prevents inherited complexity, hidden coupling,
and accidental leakage of private material into a public codebase.

### III. Agent Harness Before Loop Automation

The first phase builds a clean Agent Harness Runtime foundation with clear
runtime boundaries. Full loop automation is a future layer, not a current
deliverable.

- Scheduler, validator, evaluator, auto-iteration, and full loop-engineering
  automation MUST NOT be implemented in the foundation phase.
- Foundation work MUST leave explicit extension points (interfaces, events)
  where those future layers will attach, without implementing them.
- Scope creep toward loop automation MUST be deferred into future-phase specs.

**Rationale**: Loop automation built on unclear runtime boundaries hardens
those flaws; the harness must be solid before the loop is automated.

### IV. Runtime Boundary Clarity

Every runtime component MUST have clear, documented ownership and boundaries:
Agent Loop, Runtime Controller, Dispatcher, Tool Gateway, Skill Execution
Profile, Runtime Event Bus, Memory, Checkpoint, Artifact Store,
Observability, and Human Approval.

- Each component MUST have a single documented responsibility and owner
  boundary; overlapping ownership MUST be resolved in the spec before
  implementation.
- Cross-component interaction happens only through declared interfaces or
  runtime events — never through reach-through internal access.
- A change that blurs a boundary MUST be accompanied by an ADR updating the
  boundary definition.

**Rationale**: The control plane's value is predictable, observable agent
behavior; that is impossible when component responsibilities are ambiguous.

### V. Tool Gateway Ownership

All tool-related concerns MUST be unified behind the Tool Gateway boundary:
tool registry, tool resolving, permission checks, MCP adapter, internal tool
adapter, execution, timeout, error normalization, and artifact extraction.

- No component other than the Tool Gateway may resolve, authorize, or execute
  tools.
- Tool errors crossing the gateway boundary MUST be normalized into the
  gateway's error model; raw adapter errors MUST NOT leak to callers.
- New tool sources (e.g., a new adapter type) MUST be added inside the
  gateway, never as bypass paths.

**Rationale**: A single chokepoint for tool execution is what makes
permissions, timeouts, observability, and error handling enforceable.

### VI. Runtime Event Bus Ownership

Streaming, history, trace, frontend step display, and observability MUST
consume normalized runtime events from the Runtime Event Bus.

- The Agent Loop MUST NOT format frontend-specific events; it emits
  normalized runtime events only.
- Consumers (UI, history, trace, observability) adapt normalized events to
  their own needs on their side of the bus.
- Event schema changes MUST be treated as contract changes: versioned,
  specified, and tested.

**Rationale**: One normalized event stream keeps every consumer consistent
and lets new consumers attach without touching the Agent Loop.

### VII. Public-Safe Documentation

Committed files MUST be safe for a public repository.

- Internal company paths, private project/repo names, company-specific
  names, internal network addresses or IPs, API keys, tokens, secrets, and
  raw legacy references MUST NOT appear in committed code or docs.
- The local `openspec/` directory is a private reference source only; it is
  gitignored and MUST NOT be committed, and its raw content MUST NOT be
  copied into public project files.
- Reviews MUST include a public-safety check on every changed file.

**Rationale**: This repository is public; one leaked internal detail is
permanent in git history.

### VIII. No SDK Replacement

LoopPlane's custom runtime concept MUST NOT be replaced by LangGraph,
LangChain, CrewAI, AutoGen, the OpenAI Agents SDK, or similar agent
frameworks.

- External frameworks MAY be studied for design insight.
- The runtime core (Agent Loop, Runtime Controller, Dispatcher, Tool
  Gateway, Runtime Event Bus) MUST remain LoopPlane's own clean
  architecture; adopting a framework as the runtime core requires a
  constitution amendment, not just an ADR.

**Rationale**: The project's purpose is a purpose-built, fully owned control
plane; delegating the core to an external framework forfeits that control.

### IX. Claude Code-Like Reference, Not Clone

Claude Code-like runtime concepts MAY inform the architecture, but
implementation details MUST NOT be blindly copied.

- Borrowed concepts MUST be re-derived through LoopPlane's own specs and
  justified on their own merits.
- Where LoopPlane intentionally diverges from the reference concept, the
  divergence SHOULD be recorded in the relevant spec or ADR.

**Rationale**: Reference architectures accelerate design, but cloning
imports assumptions that may not fit LoopPlane's control-plane goals.

### X. Testable Evolution

Each implementation phase MUST include tests, validation, and rollback
guidance. Incremental changes are preferred over big-bang rewrites.

- A phase is not complete until its behavior is covered by automated tests
  and its validation steps are documented.
- Every phase MUST document how to roll back (revert strategy, feature
  isolation, or migration undo).
- Large rewrites MUST be decomposed into independently verifiable
  increments.

**Rationale**: A control plane for agents must itself be verifiable and
reversible; untested or irreversible changes undermine trust in the runtime.

## Reference Material & Confidentiality Constraints

- The local `openspec/` directory exists only as a private reference source.
  It MUST remain gitignored, MUST NOT be modified by tooling in this
  repository, and MUST NOT be committed in raw form.
- Knowledge extracted from private references MUST be rewritten into
  public-safe specs, plans, or ADRs before entering the repository
  (see Principles II and VII).
- Secrets and credentials MUST live only in local environment files
  (e.g., `.env`, already gitignored), never in committed files.

## Development Workflow & Quality Gates

- The project follows the Spec Kit workflow: constitution → specify →
  clarify → plan → tasks → implement, with artifacts under `specs/`.
- `/speckit-plan` MUST evaluate the Constitution Check gate against this
  document before Phase 0 research and re-check it after design.
- Reviews MUST verify, at minimum: traceability to an approved artifact
  (Principle I), runtime boundary integrity (Principles IV–VI),
  public-safety of all changed files (Principle VII), and presence of
  tests, validation, and rollback guidance (Principle X).
- Violations that cannot be resolved MUST be recorded in the plan's
  Complexity Tracking table with an explicit justification.

## Governance

- This constitution supersedes other development practices in this
  repository. Where guidance conflicts, the constitution wins.
- **Amendments**: any change to this document MUST be proposed in a PR that
  states the motivation, the semantic version bump, and the migration or
  propagation impact on `.specify/templates/` and existing specs.
- **Versioning policy** (semantic):
  - MAJOR — backward-incompatible governance or principle removals or
    redefinitions;
  - MINOR — new principle or section added, or materially expanded guidance;
  - PATCH — clarifications, wording, and non-semantic refinements.
- **Compliance review**: every PR review MUST include a constitution
  compliance check; deviations require justification in Complexity Tracking
  or a constitution amendment.

**Version**: 1.0.0 | **Ratified**: 2026-06-13 | **Last Amended**: 2026-06-13
