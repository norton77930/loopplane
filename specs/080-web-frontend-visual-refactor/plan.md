# Implementation Plan: Web Frontend Visual Refactor

**Branch**: 080-web-frontend-visual-refactor | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from specs/080-web-frontend-visual-refactor/spec.md

## Summary

Refactor the existing Web presentation into a focused, responsive agent workspace while preserving every current backend, transport, state, and Desktop-consumer contract. Work is incremental and test-first: freeze shared contracts, repair visible state defects, introduce semantic tokens and local icons, then rebuild the shell, chat surfaces, full-page Settings, adaptive inspection, and accessibility behavior without adding dependencies.

## Technical Context

**Language/Version**: TypeScript 5.6, React 18.3, CSS
**Primary Dependencies**: Existing React, React DOM, Markdown dependencies; no additions
**Storage**: Existing browser preferences only; no new persisted data
**Testing**: Vitest with jsdom and Testing Library, TypeScript strict checking, Vite build, Desktop consumer tests/typecheck, manual browser viewport matrix
**Target Platform**: Browser SPA and source-compatible shared components consumed by Electron Desktop
**Project Type**: Frontend-only presentation refactor with Desktop compatibility
**Performance Goals**: No added network requests or vendor chunk; immediate shell interactions; streaming does not trigger whole-page layout changes
**Constraints**: Preserve Web API, REST/SSE transport, event reducer, auth, defaults, public exports, and Desktop imports; do not modify backend, schemas, Tool Gateway, openspec, or verified 076 artifacts; do not add dependencies
**Scale/Scope**: Login, shell, sessions, chat, composer, six Settings categories, four inspection categories, two locales, two themes, and shared Desktop consumers

## Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Spec-First Development | PASS | 080 artifacts and tasks precede production edits. |
| II. Greenfield Implementation | PASS | Orion concepts are re-derived; no code is copied. |
| IV. Runtime Boundary Clarity | PASS | Presentation consumes existing boundaries only. |
| V. Tool Gateway Ownership | PASS | Tool behavior is unchanged. |
| VI. Runtime Event Bus Ownership | PASS | Existing events and reducer semantics remain unchanged. |
| VII. Public-Safe Documentation | PASS | No private paths, secrets, credentials, or raw material. |
| VIII. No SDK Replacement | PASS | No framework or runtime substitution. |
| IX. Reference, Not Clone | PASS | Patterns are independently specified. |
| X. Testable Evolution | PASS | Work is independently verifiable and reversible. |

## Project Structure

### Documentation

- specs/080-web-frontend-visual-refactor/spec.md
- specs/080-web-frontend-visual-refactor/plan.md
- specs/080-web-frontend-visual-refactor/research.md
- specs/080-web-frontend-visual-refactor/data-model.md
- specs/080-web-frontend-visual-refactor/quickstart.md
- specs/080-web-frontend-visual-refactor/contracts/ui-components.md
- specs/080-web-frontend-visual-refactor/checklists/requirements.md
- specs/080-web-frontend-visual-refactor/tasks.md

### Source Code

- apps/web/src/App.tsx: view orchestration and preserved transport/state wiring
- apps/web/src/styles.css: semantic tokens, layout, responsive and component styles
- apps/web/src/components/AppShell.tsx: collapsible shell and adaptive panel slots
- apps/web/src/components/Sidebar.tsx: session navigation and secondary actions
- apps/web/src/components/ChatHeader.tsx: identity, run state, compact actions
- apps/web/src/components/Composer.tsx: integrated input surface
- apps/web/src/components/MessageList.tsx: message and empty-state presentation
- apps/web/src/components/InspectionPanel.tsx: read-only adaptive context panel
- apps/web/src/components/CapabilitySettingsView.tsx: settings orchestration
- apps/web/src/components/icons/Icons.tsx: local accessible icons
- apps/web/src/components/settings/: category-focused private Settings components
- apps/web/src/__tests__/: behavior and compatibility tests
- apps/desktop/src/__tests__/App.test.tsx: shared Web consumer contract

**Structure Decision**: Keep existing entry, reducer, client, and public component filenames. Split only the oversized Settings implementation into category-focused private components, add one local icon module, and keep global CSS responsible for reset, tokens, and layout while component classes stay scoped.

## Phase 0 Research Decisions

See [research.md](research.md). The plan selects incremental CSS tokens, React-local view state, full-page Settings, adaptive inline or overlay inspection, local SVG icons, and manual real-browser acceptance without new packages.

## Phase 1 Design

- Presentation state and transitions: [data-model.md](data-model.md)
- Shared compatibility contract: [contracts/ui-components.md](contracts/ui-components.md)
- Validation and rollback: [quickstart.md](quickstart.md)

## Post-Design Constitution Check

All pre-design gates remain PASS. The design introduces no migration, public API, runtime event, default-value, gateway, or dependency change. Desktop compatibility is protected through unchanged imports and consumer tests.

## Complexity Tracking

No constitution violations require justification.
