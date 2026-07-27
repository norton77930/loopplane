# Feature Specification: Web Frontend Visual Refactor

**Feature Branch**: 080-web-frontend-visual-refactor
**Created**: 2026-07-13
**Status**: Draft
**Input**: Refactor LoopPlane Web using Orion Chat Web as the primary visual reference and selected Cowork interaction patterns, changing frontend presentation only.

## User Scenarios & Testing

### User Story 1 - Focused Conversation Workspace (Priority: P1)

A signed-in user can navigate sessions, read a conversation, inspect run status, attach files, choose a model, and send or stop a turn from a calm workspace on desktop, tablet, or mobile.

**Why this priority**: Conversation is the primary workflow. Fixed columns, scattered controls, and weak hierarchy make routine work feel like an engineering console.

**Independent Test**: At desktop, tablet, and mobile widths, start or select a conversation, submit an attachment and prompt, observe streaming and tool activity, then stop or continue without hidden controls.

**Acceptance Scenarios**:

1. **Given** a desktop viewport, **When** the app opens, **Then** the collapsible sidebar, focused chat, integrated composer, and optional inspection panel fit without horizontal overflow.
2. **Given** a mobile viewport, **When** sessions or inspection opens, **Then** it is a dismissible drawer and chat remains a readable single column.
3. **Given** an empty conversation, **When** the user arrives, **Then** the composer and example prompts form a centered starting experience.
4. **Given** a running turn, **When** messages, tools, approvals, questions, or errors appear, **Then** status and actions remain distinct and keyboard reachable.

---

### User Story 2 - Scalable Settings and Inspection (Priority: P2)

A user can move between chat, capability settings, and read-only inspection without losing conversation state or confusing mutable settings with runtime metadata.

**Why this priority**: Horizontal settings tabs and a fixed inspection column do not scale to existing capabilities or planned controls.

**Independent Test**: From an active conversation, open Settings, navigate all categories, return to chat, then open each inspection category and verify conversation, draft, streaming, and scroll state remain intact.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** Settings opens, **Then** a full-page workspace with vertical navigation and a clear return appears.
2. **Given** a non-wide viewport, **When** inspection opens, **Then** it overlays chat instead of shrinking it below a readable width.
3. **Given** a request failure, **When** it is shown, **Then** failure is distinguishable from empty data or policy-controlled read-only state.

---

### User Story 3 - Consistent Accessible Interaction (Priority: P3)

A keyboard, screen-reader, reduced-motion, or high-zoom user can complete login, session, chat, settings, inspection, approval, and question flows with consistent feedback.

**Why this priority**: A visual refactor must improve usability rather than only colors and spacing.

**Independent Test**: Complete primary workflows with keyboard-only navigation at 200% zoom and reduced motion, verifying focus, dialog behavior, announcements, and reflow.

**Acceptance Scenarios**:

1. **Given** keyboard-only navigation, **When** controls and dialogs are traversed, **Then** focus is visible, ordered, trapped only when appropriate, and returned after close.
2. **Given** a screen reader, **When** streaming, loading, success, or failure changes, **Then** relevant state is announced without replaying the whole conversation.
3. **Given** reduced motion or 200% zoom, **When** the app is used, **Then** essential information and actions remain available without clipping.

### Edge Cases

- Titles, labels, translated copy, messages, and tool output are unusually long.
- Sidebar, inspection, or Settings changes while a response streams.
- The viewport changes while a drawer or modal is open.
- Attachments finish, fail, or are removed near submission.
- The active session model differs from the future-session preference.
- Shared Web components render inside Desktop.

## Requirements

### Functional Requirements

- **FR-001**: The Web experience MUST use a consistent hierarchy, spacing system, typography scale, semantic color system, focus treatment, and light/dark theme.
- **FR-002**: The session sidebar MUST collapse on wide screens and become a dismissible drawer on narrow screens.
- **FR-003**: Secondary session actions MUST remain keyboard discoverable without permanently crowding every row.
- **FR-004**: The header MUST prioritize conversation identity and run state while grouping workspace, model, usage, theme, language, settings, and inspection actions consistently.
- **FR-005**: The composer MUST combine prompt entry, model selection, attachments, commands, and send or stop actions as one coherent surface.
- **FR-006**: Empty conversations MUST provide a centered entry point while reusing the normal composer behavior.
- **FR-007**: User, assistant, reasoning, tool, approval, question, termination, and error content MUST have distinct but related presentation.
- **FR-008**: Settings MUST be a full-page workspace with vertical category navigation, clear return, and narrow-screen category access.
- **FR-009**: Opening and closing Settings MUST preserve session, draft, streaming, message, and scroll state.
- **FR-010**: Inspection MUST remain read-only with Skills, Tools, MCP, and Memory, using an inline panel only when enough chat width remains and otherwise using an overlay.
- **FR-011**: Loading, empty, error, success, disabled, and policy-controlled read-only states MUST be visually distinct.
- **FR-012**: Submitted attachments MUST leave composer state and MUST NOT reappear unless attached again.
- **FR-013**: Model presentation MUST distinguish the active session model from the future-session preference.
- **FR-014**: Session rows MUST remain horizontal and readable without conflicting global styles.
- **FR-015**: Primary workflows MUST support keyboard navigation, visible focus, correct dialog focus trap and return, accessible names, and suitable live regions.
- **FR-016**: The app MUST reflow without horizontal page overflow at 375, 768, 1024, and 1440 CSS-pixel widths and at 200% zoom.
- **FR-017**: Motion MUST respect reduced-motion preference.
- **FR-018**: English and Traditional Chinese MUST remain available, and document language MUST follow the locale.
- **FR-019**: Existing authentication, session, streaming, approval, question, capability, inspection, model, attachment, and localization behavior MUST remain compatible.
- **FR-020**: Public Web component exports consumed by Desktop, including message and dialog components and shared state or API types, MUST remain source compatible.
- **FR-021**: The feature MUST NOT change backend endpoints, public API contracts, event or checkpoint schemas, gateway behavior, defaults, or permission semantics.
- **FR-022**: The feature MUST NOT add dependencies; required icons MUST use a small local accessible icon set.
- **FR-023**: The feature MUST include automated regression coverage, responsive browser acceptance coverage, Desktop consumer checks, manual visual guidance, and a presentation-only rollback path.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can start a conversation, select a model, attach a file, send a prompt, and stop a turn at 375, 768, 1024, and 1440 widths without overflow or unreachable controls.
- **SC-002**: Users can reach any Settings category within two navigation actions after opening Settings and return to the unchanged conversation in one action.
- **SC-003**: Inline inspection never reduces the chat reading column below 560 CSS pixels.
- **SC-004**: Keyboard-only users can complete login, session selection, submission, approval, question response, settings navigation, inspection navigation, and close actions with visible focus.
- **SC-005**: Automated checks cover loading, empty, error, success, disabled, and read-only presentation for Settings and inspection.
- **SC-006**: Existing Web and Desktop suites remain green, and Desktop compiles its current shared Web imports without source changes.
- **SC-007**: Manual review confirms light/dark, English/Traditional Chinese, reduced motion, and 200% zoom across the representative screen matrix.

## Assumptions

- Existing React, TypeScript, CSS, reducer, transport, API client, theme, localization, and tests remain in place.
- Orion Chat Web is a reference only; Cowork patterns are limited to full-page Settings, adaptive right panel, and centered empty state.
- This feature executes before roadmap unit 077 while retaining number 080; existing roadmap numbers do not change.
- Desktop-only projects, collaboration, backup, and native chrome stay out of scope.
- Agent controls, workspace files, artifacts, budgets, permissions, and suggestions stay owned by roadmap unit 077.
