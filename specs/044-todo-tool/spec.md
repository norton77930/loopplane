# Feature Specification: Agent Task List (`todo_write`)

**Feature Branch**: `044-todo-tool`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "An agent-facing task-list tool (`todo_write`) on the Internal Tool Adapter so the model can track multi-step work during a run. Ordered list of items, each with a description and a status (pending / in_progress / completed); calling the tool replaces the current list (set-the-whole-list). Per-run state, metadata-only, Gateway-only. Unit 044, Tier-1; closes gap G1 vs reference agent harnesses. Additive, no event-schema/content-model change, no ADR."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent records and updates a multi-step plan (Priority: P1)

While working a request that takes several steps, the agent records an ordered list of todo items — each a short description with a status — so it can lay out its plan and then mark items in progress and done as it works. Re-calling the tool with the full, updated list keeps the plan current.

**Why this priority**: This is the core value. A working task list gives the agent an explicit place to plan and track multi-step work, which the reference agent harnesses provide and LoopPlane currently lacks (gap G1). It improves follow-through on complex requests.

**Independent Test**: Drive a run where the agent calls the tool with a list, then again with changed statuses; confirm the latest submitted list is the one retained and returned. Delivers the planning/tracking value on its own.

**Acceptance Scenarios**:

1. **Given** a run with the tool available, **When** the agent submits a list of items each carrying a status, **Then** the tool accepts it and returns the recorded list to the agent.
2. **Given** a previously recorded list, **When** the agent submits a new full list, **Then** the new list fully replaces the prior one (set-the-whole-list semantics; no merge).
3. **Given** a recorded list, **When** the agent resubmits it with an item moved to `in_progress` or `completed`, **Then** the updated statuses are retained and returned.

---

### User Story 2 - Host or observer sees the current plan as metadata (Priority: P2)

A host or observer can read the agent's current todo list — item descriptions and their statuses — as metadata only, with no conversation content or secrets, to monitor what the agent is doing and how far along it is.

**Why this priority**: Observability parity. The list is only useful for oversight if a host can surface it; this keeps LoopPlane's metadata-only, leak-free observability posture.

**Independent Test**: After the agent records a list, inspect the run's observable surface and confirm the items and statuses appear as metadata with no conversation content or secrets.

**Acceptance Scenarios**:

1. **Given** the agent has recorded a list, **When** the host inspects the run, **Then** it can read the current items and their statuses as metadata only.

---

### User Story 3 - Tool is governed like every other tool (Priority: P3)

The task-list tool is subject to the same governance as all tools — permission policies, plan-mode read-only handling, and hooks — so a host can allow, deny, or observe its use.

**Why this priority**: Consistency and governance. Every capability must flow through the single Tool Gateway and honor the existing decision/governance layers.

**Independent Test**: With a permission policy that denies the tool, the agent's call is denied with a normalized outcome and no state change; existing governance behavior is unaffected for other tools.

**Acceptance Scenarios**:

1. **Given** a permission policy that denies the tool, **When** the agent calls it, **Then** the call is denied with a normalized error and the current list is unchanged.

---

### Edge Cases

- **Empty list submitted**: valid — it clears the current list.
- **Invalid status** (a value outside pending / in_progress / completed): rejected with a clear normalized error; the prior list is unchanged.
- **Malformed input** (missing required field, wrong shape): rejected with a normalized validation error; no state change.
- **Oversized list** (more items than the allowed maximum): rejected with a normalized error; the prior list is unchanged.
- **First call with no prior list**: succeeds and establishes the list.
- **Tool not enabled / unknown**: handled by the standard unknown-tool path, with no special behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a tool, reachable only through the Tool Gateway (Constitution V), that lets the agent record an ordered list of todo items, where each item has a text description and a status of `pending`, `in_progress`, or `completed`.
- **FR-002**: The tool MUST use set-the-whole-list semantics — each call replaces the current list with exactly the submitted list; there is no partial update or merge.
- **FR-003**: The current list MUST be retained as per-run state for the duration of the run and be available to subsequent calls within that run.
- **FR-004**: The tool MUST return the recorded list (items and statuses) to the agent as its result so the agent can confirm the stored state.
- **FR-005**: The current list MUST be observable as metadata only — item descriptions and status counts — with no conversation content, secrets, or internal paths (Constitution VI/VII).
- **FR-006**: The tool MUST validate input and reject a malformed or invalid submission (unknown status, missing field, wrong shape) with a normalized error, leaving the prior list unchanged.
- **FR-007**: An empty submitted list MUST be valid and MUST clear the current list.
- **FR-008**: The number of items MUST be bounded by a reasonable maximum; a submission exceeding the bound MUST be rejected with a normalized error and leave the prior list unchanged.
- **FR-009**: The tool MUST be subject to the same governance as other tools — permission policies, the plan-mode read-only decision, and lifecycle hooks — with no special-casing.
- **FR-010**: Adding the tool MUST be additive: no change to the runtime event schema or `SCHEMA_VERSION`, the content model, the agent-loop turn cycle, the Tool Gateway pipeline, or any existing tool.
- **FR-011**: The tool MUST be part of the agent's built-in tool set wherever that set is assembled, mirroring the existing baseline tools; a run that does not call it MUST behave as it does today.

### Key Entities *(include if feature involves data)*

- **Todo item**: a single unit of work the agent is tracking — a text description plus a status (`pending`, `in_progress`, or `completed`). Its order is its position in the list.
- **Todo list**: the ordered collection of todo items for the current run; replaced in whole on each call and surfaced as metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Within a single run, the agent can record a list and later update it, and the latest submitted list is always the one retained (100% replace semantics, no residual items from prior calls).
- **SC-002**: The current list is observable as metadata with zero leakage of conversation content or secrets, verified by inspection.
- **SC-003**: 100% of malformed or invalid submissions are rejected without changing the prior list.
- **SC-004**: Runs that do not use the tool are unaffected — the existing test suite passes unchanged and no event-schema or content-model change is introduced.

## Assumptions

- The direct "user" of this tool is the agent (model) during a run; the beneficiaries are the host/embedder observing progress and the quality of multi-step task completion.
- Set-the-whole-list (replace) semantics match the reference agent harnesses; no partial-update or per-item-patch interface in this unit.
- The status vocabulary is fixed to `pending` / `in_progress` / `completed` (matching the reference harnesses); custom statuses are out of scope for this unit.
- The list is per-run state surfaced through the existing observability surface; cross-session persistence beyond the existing checkpoint mechanism is out of scope.
- The tool is a baseline built-in tool with no external dependency and no network access; it is available wherever the built-in tool set is assembled.
- No UI/frontend work is in scope for this unit; a future unit could render the metadata.
- Per Constitution IX, the concept is borrowed from the reference harnesses but re-derived through this spec; no implementation detail is copied.
