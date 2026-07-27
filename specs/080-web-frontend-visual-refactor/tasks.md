# Tasks: Web Frontend Visual Refactor

## Phase 1: Setup and Baseline

- [X] T001 Record current Web and Desktop baseline gates in specs/080-web-frontend-visual-refactor/quickstart.md
- [X] T002 Add Desktop shared-component characterization coverage in apps/desktop/src/__tests__/App.test.tsx
- [X] T003 Add Web shell characterization coverage in apps/web/src/__tests__/App.shell.test.tsx

## Phase 2: Foundational Presentation System

- [X] T004 [P] Add failing semantic icon contract tests in apps/web/src/__tests__/Icons.test.tsx
- [X] T005 [P] Add failing visual token and responsive class assertions in apps/web/src/__tests__/AppShell.test.tsx
- [X] T006 Implement the dependency-free icon module in apps/web/src/components/icons/Icons.tsx
- [X] T007 Implement semantic theme, spacing, focus, layout, and reduced-motion tokens in apps/web/src/styles.css
- [X] T008 Refactor apps/web/src/components/AppShell.tsx into presentation-only shell slots with collapsed and overlay states

## Phase 3: User Story 1 - Focused Conversation Workspace

**Goal**: Deliver the responsive conversation shell as the independently usable MVP.

**Independent Test**: Start or select a session, submit a prompt with an attachment, observe streaming and tool states, and stop or continue at representative viewport classes.

- [X] T009 [P] [US1] Add failing horizontal session-row and secondary-action tests in apps/web/src/__tests__/Sidebar.test.tsx
- [X] T010 [P] [US1] Add failing integrated composer and consumed-attachment tests in apps/web/src/__tests__/Composer.test.tsx and apps/web/src/__tests__/Attachments.test.tsx
- [X] T011 [P] [US1] Add failing active-session versus future-model preference tests in apps/web/src/__tests__/App.sessionParity.test.tsx
- [X] T012 [US1] Refactor session navigation and responsive controls in apps/web/src/components/Sidebar.tsx
- [X] T013 [US1] Refactor compact run identity and action groups in apps/web/src/components/ChatHeader.tsx
- [X] T014 [US1] Refactor the integrated input surface in apps/web/src/components/Composer.tsx and apps/web/src/components/Attachments.tsx
- [X] T015 [US1] Correct attachment consumption and model labeling orchestration in apps/web/src/App.tsx
- [X] T016 [US1] Refine empty, message, reasoning, tool, dialog, and termination hierarchy in apps/web/src/components/MessageList.tsx and related components
- [X] T017 [US1] Complete responsive shell and conversation styling in apps/web/src/styles.css

## Phase 4: User Story 2 - Scalable Settings and Inspection

**Goal**: Deliver full-page Settings and adaptive read-only inspection without losing chat state.

**Independent Test**: Open every Settings and inspection category from an active session, return to chat, and verify state preservation and distinct async states.

- [X] T018 [P] [US2] Add failing full-page Settings navigation and return tests in apps/web/src/__tests__/App.capabilities.test.tsx
- [X] T019 [P] [US2] Add failing loading, empty, error, disabled, and read-only state tests in apps/web/src/__tests__/CapabilitySettingsView.test.tsx and apps/web/src/__tests__/InspectionPanel.test.tsx
- [X] T020 [US2] Add the vertical Settings shell in apps/web/src/components/settings/SettingsLayout.tsx
- [X] T021 [US2] Split capability categories into private components under apps/web/src/components/settings/
- [X] T022 [US2] Keep apps/web/src/components/CapabilitySettingsView.tsx as the thin API and state orchestrator
- [X] T023 [US2] Refactor apps/web/src/components/InspectionPanel.tsx into adaptive inline or overlay read-only presentation
- [X] T024 [US2] Wire full-page Settings return and adaptive inspection state in apps/web/src/App.tsx and apps/web/src/components/AppShell.tsx

## Phase 5: User Story 3 - Accessible Consistent Interaction

**Goal**: Complete keyboard, locale, live-region, reduced-motion, high-zoom, and state feedback requirements.

**Independent Test**: Complete primary flows by keyboard at 200 percent zoom and reduced motion with correct focus and announcements.

- [X] T025 [P] [US3] Add failing tab semantics, focus, live-region, and document-language tests under apps/web/src/__tests__/
- [X] T026 [US3] Implement accessible tab, drawer, dialog, loading, and streaming semantics in apps/web/src/components/
- [X] T027 [US3] Synchronize document language and remaining English and Traditional Chinese chrome in apps/web/src/i18n/ and apps/web/src/index.html
- [X] T028 [US3] Complete focus-visible, high-zoom, forced-color, and reduced-motion rules in apps/web/src/styles.css

## Phase 6: Polish and Validation

- [X] T029 Run focused and full Web typecheck, test, and build gates from specs/080-web-frontend-visual-refactor/quickstart.md
- [X] T030 Run Desktop typecheck and test consumer gates from specs/080-web-frontend-visual-refactor/quickstart.md
- [X] T031 Execute and record the manual viewport, theme, locale, zoom, and reduced-motion matrix in specs/080-web-frontend-visual-refactor/quickstart.md
- [X] T032 Run public-safety and scope-diff review and document rollback readiness in specs/080-web-frontend-visual-refactor/quickstart.md
- [X] T033 Update docs/loopplane-agent-board.md only after all 080 acceptance gates pass

## Dependencies

- Phase 1 precedes all implementation.
- Phase 2 blocks User Stories 1 through 3.
- User Story 1 is the MVP and precedes the final Settings integration in User Story 2.
- User Story 3 can proceed after the relevant User Story 1 and 2 components exist.
- Phase 6 requires all selected user stories complete.

## Implementation Strategy

Deliver User Story 1 first as a working shell without backend or dependency changes. Add Settings and inspection as the next reversible slice, then apply accessibility hardening across the completed surfaces. Each implementation task follows red, green, refactor and keeps Web plus Desktop consumer gates green.
