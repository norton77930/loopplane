# Feature Specification: Web Agent Model Selection & File Attachments

**Feature Branch**: `028-web-agent-model-files` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Two capabilities the web UI still lacks versus a modern agent app: per-session model selection and file attachments. Both were initially flagged as needing a boundary ADR, but — after reviewing a working reference design — both can be delivered as **additive** changes that do **not** blur a runtime boundary, so **no constitution ADR is required** (they are like unit 027). (1) Per-session model selection is resolved entirely in the web/API layer: the host holds a small registry of pre-configured single-model hosts, a session binds a chosen model at open time and may change it between turns, and the next turn is routed to the chosen model's host, resuming the session from the shared checkpoint store — the runtime core still receives exactly one model per run. (2) File attachments use an additive upload endpoint that stores each file (scoped to its principal) and returns a reference; the message carries the reference; the agent reads the file on demand via a new read-upload tool registered inside the Tool Gateway (Constitution V explicitly allows new tools inside the gateway) — files are transient input referenced by id, not artifacts, not memory, and not embedded into the content model. Multimodal/embedded file content (an image content block) is deferred to a later unit (that would touch the content boundary). Cost/pricing is out of scope."

## Overview

The web UI (units 025–027) covers the agent conversation, the extra signals, and read-only
inspection — but it still **binds one model globally** (chosen at host-construction time, with
no per-session selection) and has **no way to attach files** to a message. Both are standard in
a modern agent app. They were initially deferred as "needs an ADR," but a review of a working
reference design showed that **both can be delivered additively, without blurring any runtime
boundary — so no constitution ADR is required** (they are like unit 027, additive over the
host/transport seams):

1. **Per-session model selection** — resolved **entirely in the web/API layer**. The host holds
   a small **registry of pre-configured single-model hosts** (one per available model, reusing
   the unit-020 adapters), exposes the **catalog** as a read endpoint, **binds a session to a
   chosen model** at open time, and lets the user **change it between turns**. The next turn is
   **routed to the chosen model's host**, which **resumes the session from the shared checkpoint
   store** (unit 021) so history is preserved. The **runtime core is untouched** — it still
   receives **exactly one model per run**.
2. **File attachments** — an **additive upload endpoint** stores each file (scoped to its
   **principal**, unit 022) and returns a **reference**; the message carries the reference; the
   agent **reads the file on demand** via a **new read-upload tool registered inside the Tool
   Gateway** (Constitution V explicitly allows new tools inside the gateway). Files are
   **transient input referenced by id** — **not** artifacts, **not** memory, and **not embedded**
   into the prompt/content model (so the content contract is unchanged). This already does **more
   than the reference**, whose web path stores the file but never feeds its content to the model.

It is **additive**: the runtime core, the one-model-per-run contract, the content model, the
Tool Gateway and Event Bus contracts, and existing endpoints are **preserved**; the new pieces
are a model catalog + per-session selection in the web/API layer, an upload endpoint, and a
gateway read-upload tool. **No ADR / maintainer gate** is needed — a reference review confirmed
the additive path. **Multimodal/embedded file content** (an image content block in the prompt)
is **deferred to a later unit** (that would touch the content boundary, Principle IV). The
design is **written fresh** with **no private or legacy UI copied** (VII), and **no external
framework** is adopted (VIII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose the model a session uses (Priority: P1)

A user opens the model selector in the composer, sees the **available models** the host offers,
and **picks the one** the session should use; they can **change it between turns**. The agent's
next run uses the chosen model.

**Why this priority**: Model choice is a core capability of a modern agent app and unblocks
using the real provider adapters (unit 020) from the UI; it is delivered additively in the
web/API layer.

**Independent Test**: With more than one model configured, the catalog endpoint lists them, the
selector shows them, choosing one makes the session's next run use it (routed to that model's
host), and the runtime receives exactly one model for that run.

**Acceptance Scenarios**:

1. **Given** the host has multiple models configured, **When** the user opens the model selector, **Then** the available models are listed and the current selection is indicated.
2. **Given** a selected model, **When** the user sends a prompt, **Then** the run uses that model.
3. **Given** an in-progress session, **When** the user changes the model between turns, **Then** the next turn uses the new model (the session resumes from the shared checkpoint) and the runtime still receives exactly one model per run.

### User Story 2 - Attach a file to a message (Priority: P2)

A user attaches one or more files to a message (drag-drop or picker), sees **upload progress**,
and sends; the agent can **read the attached files on demand** as input to the run.

**Why this priority**: Attachments are a powerful capability; delivered additively (an upload
endpoint + a gateway read-upload tool), and the agent reading files via a tool is the
established Claude-Code-style pattern this runtime already uses.

**Independent Test**: A file attached in the composer is uploaded (with progress), stored
(scoped to the principal), and referenced on the message; the agent can read it via the
read-upload tool during the run; errors (too large, failed upload) are surfaced.

**Acceptance Scenarios**:

1. **Given** the composer, **When** the user attaches one or more files and sends, **Then** each file is uploaded with progress and the message carries the attachment references.
2. **Given** an attached file, **When** the run executes, **Then** the agent can read the file content on demand via the read-upload tool (inside the Tool Gateway).
3. **Given** an upload error (e.g., too large or a network failure), **When** it occurs, **Then** a clear error is surfaced and the message is not sent with a missing attachment.

### Edge Cases

- **Only one model configured** → the selector still works (shows one) or hides gracefully; no error.
- **A model becomes unavailable** between selection and run → a clear error, not a silent wrong-model run.
- **Changing the model mid-run** → disallowed/deferred to the next turn (the runtime gets one model per run).
- **A session resumed on a different model's host** → it loads from the shared checkpoint store and continues; history is intact.
- **A very large file / unsupported type** → rejected with a clear message (configurable limits).
- **Multiple attachments** → all upload (batch), with per-file progress and error.
- **The agent never reads an attachment** → no error; the file simply goes unread (the reference is harmless).
- **Auth / per-principal scoping** → uploads and model selection honor the existing auth boundary; an attachment is scoped to its owner.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web/API host MUST expose a **read-only catalog of available models** the host operator has configured.
- **FR-002**: The UI MUST let the user **see the available models and select** which model a **session** uses, with the current selection indicated.
- **FR-003**: The selected model MUST apply to the session's runs, and the user MUST be able to **change it between turns**.
- **FR-004**: The runtime core MUST receive **exactly one model per run** — per-session selection is resolved **in the web/API layer** (routing the session's next turn to the chosen model's pre-configured host, resuming from the **shared checkpoint store**); the runtime/Agent Loop is **unchanged**.
- **FR-005**: The UI MUST let the user **attach one or more files** to a message (drag-drop or picker) with **upload progress** and **error handling**.
- **FR-006**: The web/API host MUST provide an **upload endpoint** that stores an attachment **scoped to its principal** and returns a **reference**, and a message MUST be able to carry **attachment references**.
- **FR-007**: The agent MUST be able to **read an attached file on demand** via a **read-upload tool registered inside the Tool Gateway** — files are **transient input referenced by id**, **not** embedded into the content model and **not** persisted as artifacts or memory.
- **FR-008**: Model selection and uploads MUST honor the **existing auth boundary** and per-principal scoping.
- **FR-009**: Configurable **limits** (file size/type; model availability) MUST be enforced with clear errors; the runtime core, the one-model-per-run contract, the content model, the Tool Gateway (V), and the Event Bus (VI) contracts MUST stay **additive/preserved**.
- **FR-010**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied**.

### Key Entities

- **Model catalog entry**: an available model the host offers (identifier/label, and the pre-configured host that serves it) — metadata only at the API.
- **Session model selection**: the model a session is currently bound to (changeable between turns; one per run; routed at the web/API layer).
- **Attachment**: an uploaded file stored as a per-principal blob, referenced by id, **read on demand via a Tool Gateway tool** (transient input — not artifact, memory, or embedded content).

### Out of Scope

- **Multimodal / embedded file content** (an image or file content block placed into the prompt) — that **would** touch the content boundary (Principle IV) and need an ADR; **deferred to a later unit**. This unit delivers **tool-read** access for text/document files.
- **Cost / pricing** (token-to-currency) — not part of this unit.
- **Mid-run model switching** — the runtime receives one model per run; switching applies to the next turn.
- **Persisting attachments as artifacts or memory** — files are transient input only.
- **Adopting an external agent framework** — the runtime core stays LoopPlane's own (Principle VIII).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With multiple models configured, a user can **see and select** the session's model and **change it between turns**; each run uses the selected model and the runtime receives **exactly one model per run**.
- **SC-002**: A user can **attach file(s)** to a message (with progress and error handling); the agent can **read** them on demand via the **gateway read-upload tool**.
- **SC-003**: The change is **additive** — **no runtime boundary is blurred and no constitution ADR is needed**: the model stays **per-host, one per run** (selection routed in the web/API layer), and files are delivered by an **upload endpoint + a gateway tool** with **no content-model change**.
- **SC-004**: The runtime core, the one-model-per-run contract, the content model, the Tool Gateway, and the Event Bus are **preserved**; existing tests stay green and the **Python suite passes**.
- **SC-005**: The `apps/web` gate (type check + tests + build) is **green**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Additive designs (confirmed by a reference review)** — neither capability blurs a runtime boundary, so **no ADR is required**:
  - **Model**: the host holds a **registry of pre-configured single-model hosts** (reusing the unit-020 adapters); a session binds one and the web/API layer **routes** its next turn to that host, **resuming from the shared checkpoint store** (unit 021). The runtime keeps **one model per run** — it is never made to switch models internally.
  - **Files**: an **upload endpoint** stores a per-principal blob (unit 022 scoping); the agent reads it via a **read-upload tool inside the Tool Gateway** (Constitution V — new tools belong in the gateway). Files are **transient input referenced by id**, not embedded content, artifacts, or memory.
- **Reuses prior units**: 020 (model adapters), 021 (shared checkpoint store), 022 (principal scoping), 001 (Tool Gateway), and the 025 shell (the model selector + attachment UI live in the composer); sequenced after 027.
- **Additive, reversible**: removing the selector/upload restores the prior single-model, text-only behavior (Constitution X rollback).
- **Fresh design, public-safe (VII)**; **no SDK replacement (VIII)**; **multimodal embedded content deferred** (it, and only it, would need a Principle IV ADR).
