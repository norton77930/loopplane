# Implementation Plan: Web Session Management

**Branch**: `030-web-session-management` (main-only autopilot) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/030-web-session-management/spec.md`

## Summary

Make the sessions sidebar product-grade and let a user **rename** and **delete** sessions, with
titles + recency grouping. This is the sprint's one **full-stack, additive, no-ADR** slice. The
durable session record already carries a **title field** (`SessionMetaPayload.label`) set once at
creation and a per-owner scoping (unit 022); this unit **additively** extends the `CheckpointStore`
interface so a title can be **updated** and a session can be **deleted**, threads those through the
existing **webapi → host → controller → checkpoint store** chain, and surfaces titles + grouping +
rename + delete in the sidebar. No Tool Gateway (V) or Event Bus (VI) change → **no ADR**.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.6 + React 18 (frontend)

**Primary Dependencies**: FastAPI + Pydantic (web/API host); React + Vite + Vitest (`apps/web`). **No new dependency.**

**Storage**: the unit-021 checkpoint store — `FileCheckpointStore` (default) and `SqliteCheckpointStore`; durable, append-only session records (`SessionMetaRecord` carries `label`).

**Testing**: `pytest` (checkpoint unit on both backends, host/controller unit, webapi integration incl. non-owner 404); `vitest` (`apps/web`).

**Target Platform**: browser SPA over the unit-011 web/API host.

**Project Type**: web application (frontend + backend), additive over existing layers.

**Performance Goals**: none beyond existing; rename/delete are O(1)-ish metadata ops.

**Constraints**: additive only; webapi import boundary preserved (`loopplane.{events,host,webapi}`); owner-scoped (non-owner → 404); mypy `--strict`, 88-char lines.

**Scale/Scope**: per-principal session lists; sidebar grouping by recency.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First** ✅ — traces to `spec.md` (FR-001…FR-010, SC-001…SC-007).
- **II. Greenfield** ✅ — written fresh; no legacy/private code copied.
- **IV. Runtime Boundary Clarity** ✅ — extends the **declared** `CheckpointStore` interface additively (`set_title`, `delete_session`); cross-component access stays through declared interfaces (webapi → host → controller → store); **no reach-through**, so **no boundary is blurred → no ADR**.
- **V. Tool Gateway** ✅ — untouched; no tool is resolved/authorized/executed.
- **VI. Event Bus** ✅ — untouched; no event emitted or consumed (session-metadata CRUD only).
- **VII. Public-Safe** ✅ — no private path/name/IP/secret; no private/legacy UI copied.
- **X. Testable Evolution** ✅ — tests on both store backends + host/controller + webapi (incl. non-owner 404) + frontend; **rollback = revert the diff** (drop the two store methods, the controller/host methods, the two routes, the `SessionSummaryView` field additions; restore the pinned `{session_id, label}` assertions).

**Result: PASS — no ADR, no Complexity Tracking entries.** (Matches the additive posture of units 027/028.)

## Project Structure

### Documentation (this feature)

```text
specs/030-web-session-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── session-management.md   # Phase 1 — PATCH/DELETE + extended list contract
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/loopplane/
├── checkpoint/
│   ├── base.py          # CheckpointStore Protocol: + set_title, + delete_session; SessionSummary unchanged
│   ├── file.py          # FileCheckpointStore: append fresh meta on set_title; _read_meta -> LAST meta; delete_session removes the session dir (idempotent)
│   └── sqlite.py        # SqliteCheckpointStore: insert fresh meta; meta-pick -> LAST; delete_session = DELETE WHERE session_id
├── controller/
│   └── controller.py    # + set_session_title / delete_session (delegate to store; raise without store; update in-memory _Session.label / pop live session)
├── host/
│   └── host.py          # + set_session_title / delete_session (re-expose)
└── webapi/
    ├── app.py           # + PATCH /v1/sessions/{id} (rename) + DELETE /v1/sessions/{id}; both via _owned_or_404; DELETE cancels live entry first
    └── models.py        # + RenameRequest; SessionSummaryView (+ _SummaryLike) -> {session_id, label, last_active_at, created_at}

apps/web/src/
├── api/types.ts         # SessionSummary -> { session_id, label, last_active_at, created_at }
├── api/client.ts        # + renameSession(id,title) [PATCH], + deleteSession(id) [DELETE]
├── components/Sidebar.tsx   # title (label ?? id), Today/Yesterday/Earlier grouping, per-session overflow menu (rename inline, delete+confirm)
├── lib/sessionGroups.ts # pure date-bucket helper (Today/Yesterday/Earlier)
└── App.tsx              # wire rename/delete -> client + refreshSessions; handle deleting the open session

tests/
├── unit/ (or alongside existing checkpoint tests)   # set_title last-wins + delete on BOTH backends
├── contract/test_webapi_boundary.py                 # update pinned SessionSummaryView field set; boundary still green
└── integration/test_webapi_session_mgmt.py          # PATCH/DELETE happy path + non-owner 404 + unknown id 404
```

**Structure Decision**: Additive edits to the existing checkpoint / controller / host / webapi
layers (no new module except a tiny frontend `lib/sessionGroups.ts` pure helper), plus the
sidebar wiring — matching the layering of units 027/028.

## Complexity Tracking

> No Constitution violations — no entries. (Additive interface extension; no ADR.)
