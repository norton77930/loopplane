# Feature Specification: Web Agent Model Selection & File Attachments

**Feature Branch**: `028-web-agent-model-files` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Two capabilities the web UI still lacks versus a modern agent app, both touching runtime boundaries (so each needs a boundary ADR, not just a spec): (1) per-session model selection — let the user see the available models and choose which one a session uses, changeable between turns, with the runtime still receiving exactly one model per run (selection resolved at the host layer, not by switching models inside the Agent Loop); (2) file attachments — let the user attach one or more files to a message, stored via an upload endpoint and referenced as transient run input the agent can read. Because model binding and file ownership touch the runtime boundary (Constitution IV), this unit's plan MUST carry the ADR(s) updating those boundary definitions, recorded in Complexity Tracking and approved by the maintainer before implement; the runtime core, the Tool Gateway, and the Event Bus contracts stay additive/preserved. Cost/pricing is out of scope here."

## Overview

The web UI (units 025–027) covers the agent conversation, the extra signals, and read-only
inspection — but it still **binds one model globally** (chosen at host-construction time, with
no per-session selection) and has **no way to attach files** to a message. Both are standard
in a modern agent app and both were deferred from earlier units because, unlike 025–027, they
**touch runtime boundaries** and therefore require an **architecture decision record (ADR)**
under **Constitution Principle IV (Runtime Boundary Clarity)** — "a change that blurs a
boundary MUST be accompanied by an ADR updating the boundary definition."

This unit adds those two capabilities **behind their boundary ADRs**:

1. **Per-session model selection** — the user sees the **available models** (a catalog the
   host operator configures) and chooses which model a **session** uses, changeable between
   turns. The selection is **resolved at the host layer**: the runtime core still receives
   **exactly one model per run** (the Agent Loop does not switch models mid-run), so the
   runtime's one-model-per-run contract is **preserved**; the host gains an **additive** way
   to pick which configured model a session binds.
2. **File attachments** — the user attaches one or more files to a message; an **upload
   endpoint** stores each and returns a **reference**; the message carries attachment
   references that the agent can read. Files are modeled as **transient run input** (not
   artifacts, not memory) — a boundary the ADR makes explicit.

Because these touch the runtime boundary, this unit is **governance-gated**: its `plan` MUST
include the ADR(s) and record them in **Complexity Tracking**, and the **maintainer approves
the boundary decision before implement** (so under autopilot this unit pauses for that
approval — it is **not** a clean, gate-free unit like 025–027). The change is otherwise kept
**additive**: the Tool Gateway (V) and the Event Bus (VI) contracts are preserved, no external
framework is adopted (VIII), and the design is **written fresh** with **no private or legacy
UI copied** (VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose the model a session uses (Priority: P1)

A user opens the model selector in the composer, sees the **available models** the host
offers, and **picks the one** the session should use; they can **change it between turns**. The
agent's next run uses the chosen model.

**Why this priority**: Model choice is a core capability of a modern agent app and unblocks
using the real provider adapters (unit 020) from the UI; it is the more contained of the two
boundary changes (host-layer selection, runtime contract preserved).

**Independent Test**: With more than one model configured, the catalog endpoint lists them,
the selector shows them, choosing one makes the session's next run use it, and the runtime
receives exactly one model for that run.

**Acceptance Scenarios**:

1. **Given** the host has multiple models configured, **When** the user opens the model selector, **Then** the available models are listed and the current selection is indicated.
2. **Given** a selected model, **When** the user sends a prompt, **Then** the run uses that model.
3. **Given** an in-progress session, **When** the user changes the model between turns, **Then** the next turn uses the new model and the runtime still receives exactly one model per run.

### User Story 2 - Attach a file to a message (Priority: P2)

A user attaches one or more files to a message (drag-drop or picker), sees **upload progress**,
and sends; the agent can **read the attached files** as input to the run.

**Why this priority**: Attachments are a powerful capability but the larger boundary change
(content input, storage, lifecycle); it is sequenced after model selection.

**Independent Test**: A file attached in the composer is uploaded (with progress), stored, and
referenced on the message; the run input carries the reference and the agent can read it;
errors (too large, failed upload) are surfaced.

**Acceptance Scenarios**:

1. **Given** the composer, **When** the user attaches one or more files and sends, **Then** each file is uploaded with progress and the message carries the attachment references.
2. **Given** an attached file, **When** the run starts, **Then** the file is available to the agent as transient run input.
3. **Given** an upload error (e.g., too large or a network failure), **When** it occurs, **Then** a clear error is surfaced and the message is not sent with a missing attachment.

### Edge Cases

- **Only one model configured** → the selector still works (shows one) or is hidden gracefully; no error.
- **A model becomes unavailable** between selection and run → a clear error, not a silent wrong-model run.
- **Changing the model mid-run** → disallowed/deferred to the next turn (the runtime gets one model per run).
- **A very large file / unsupported type** → rejected with a clear message (limits are configured).
- **Multiple attachments** → all upload (batch), with per-file progress and error.
- **An attachment outlives its run** → governed by the file-lifecycle decision in the ADR (transient input, not a persisted artifact).
- **Auth / per-principal scoping** → uploads and model selection honor the existing auth boundary; an attachment is scoped to its owner.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web/API host MUST expose a **read-only catalog of available models** the host operator has configured.
- **FR-002**: The UI MUST let the user **see the available models and select** which model a **session** uses, with the current selection indicated.
- **FR-003**: The selected model MUST apply to the session's runs, and the user MUST be able to **change it between turns**.
- **FR-004**: The runtime core MUST receive **exactly one model per run** — per-session selection is resolved at the **host layer**; the Agent Loop does **not** switch models within a run (its one-model-per-run contract is preserved).
- **FR-005**: The UI MUST let the user **attach one or more files** to a message (drag-drop or picker) with **upload progress** and **error handling**.
- **FR-006**: The web/API host MUST provide an **upload endpoint** that stores an attachment and returns a **reference**, and a message MUST be able to carry **attachment references**.
- **FR-007**: Attached files MUST be modeled as **transient run input** (not artifacts, not memory) per the boundary ADR, and the agent MUST be able to **read** them during the run.
- **FR-008**: Model selection and uploads MUST honor the **existing auth boundary** and per-principal scoping.
- **FR-009**: Configurable **limits** (file size/type; model availability) MUST be enforced with clear errors; the runtime core, the Tool Gateway (V), and the Event Bus (VI) contracts MUST stay **additive/preserved**.
- **FR-010**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied**.

### Constitution & ADR (Governance) *(mandatory for this unit)*

- **CG-001**: Per-session model selection changes how the model is **bound** (today fixed at host construction). The `plan` MUST include an **ADR** that updates the **model-binding boundary** (Principle IV): the host gains an additive per-session model registry/selection; the runtime keeps **one model per run**. The ADR MUST be recorded in the plan's **Complexity Tracking** and **approved by the maintainer before implement**.
- **CG-002**: File attachments introduce a new **content input** that crosses the content/artifact/memory boundaries. The `plan` MUST include an **ADR** that defines **file ownership and lifecycle** — files are **transient run input** (distinct from the Artifact Store and from Memory) — recorded in **Complexity Tracking** and **approved by the maintainer before implement**.
- **CG-003**: These are **ADRs, not a constitution amendment** — no external framework replaces the runtime core (Principle VIII is not engaged). The Tool Gateway (V) and Event Bus (VI) remain unchanged. Under autopilot, this unit **pauses at the plan gate** for the maintainer's ADR approval.

### Key Entities

- **Model catalog entry**: an available model the host offers (identifier/label) for selection — metadata only.
- **Session model selection**: the model a session is currently bound to (changeable between turns; one per run).
- **Attachment**: an uploaded file's stored reference (name, type, size) used as transient run input.

### Out of Scope

- **Cost / pricing** (token-to-currency) — not part of this unit.
- **Mid-run model switching** — the runtime receives one model per run; switching applies to the next turn.
- **Persisting attachments as artifacts or memory** — files are transient run input only (the ADR boundary).
- **Adopting an external agent framework** — the runtime core stays LoopPlane's own (Principle VIII).
- **Streaming/multimodal model output changes** — only model **selection** and file **input** are in scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With multiple models configured, a user can **see and select** the session's model and **change it between turns**, and each run uses the selected model — the runtime receiving exactly one model per run.
- **SC-002**: A user can **attach file(s)** to a message (with progress and error handling); the run input carries the references and the agent can **read** them.
- **SC-003**: The **boundary ADRs** (model binding; file lifecycle) are written, recorded in the plan's **Complexity Tracking**, and **approved by the maintainer** before any implementation.
- **SC-004**: The change is **additive** — the runtime core's one-model-per-run contract, the Tool Gateway, and the Event Bus are **preserved**; existing tests stay green and the Python suite passes.
- **SC-005**: The `apps/web` gate (type check + tests + build) is **green**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Host-layer model selection**: the host operator configures the set of usable models; selection picks among them per session — the runtime still binds **one model per run**, so the runtime core is not made to switch models internally (the contained design that keeps Principle IV satisfiable with an additive ADR).
- **Files as transient run input**: attachments are run input, **not** persisted artifacts or memory entries; lifecycle and limits are defined in the ADR (the conservative boundary).
- **Governance-gated**: unlike 025–027, this unit requires **maintainer-approved ADRs** at the plan gate before implement; autopilot pauses here. (Per the board's stop conditions, a boundary change is a human decision point.)
- **Builds on 025–027**: the model selector lives in the composer and the attachment UI in the message input, within the established shell; sequenced after 027.
- **Additive, reversible**: removing the selector/upload restores the prior single-model, text-only behavior (Constitution X rollback).
- **Fresh design, public-safe (VII)**; **no SDK replacement (VIII)**.
