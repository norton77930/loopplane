# Research: Web Frontend Visual Refactor

## Incremental presentation architecture

**Decision**: Preserve the current React state, pure chat reducer, transports, API client, and public component names. Refactor presentation in independently testable slices.

**Rationale**: The existing behavior is broad and tested, while the user dissatisfaction is concentrated in layout, hierarchy, density, responsiveness, and Settings structure.

**Alternatives considered**: A CSS-only reskin leaves the monolithic Settings and weak information architecture intact. A Tailwind, Zustand, or full Orion-style rewrite adds dependencies and risks Desktop/source compatibility.

## Visual system

**Decision**: Extend the existing CSS custom properties into semantic background, foreground, border, accent, state, spacing, radius, shadow, typography, and focus tokens. Use warm cream and muted orange in light mode and warm charcoal in dark mode.

**Rationale**: This matches the approved visual direction without replacing the existing theme mechanism.

**Alternatives considered**: Hard-coded component colors repeat the current inconsistency. A new styling framework violates the dependency boundary.

## Navigation and view state

**Decision**: Keep navigation as local presentation state: chat and full-page Settings are mutually exclusive views; opening Settings does not unmount or reset chat state. Sidebar collapse and theme preferences may persist using existing browser preference patterns.

**Rationale**: The SPA has no URL router, and adding one is unnecessary for this presentation-only feature.

**Alternatives considered**: A modal Settings surface does not scale to six categories. New URL routes would expand scope and introduce navigation contracts.

## Adaptive shell

**Decision**: Use three layout bands: wide screens support expanded or collapsed Sidebar plus optional inline inspection; medium screens use collapsed Sidebar and inspection overlay; narrow screens use a single chat column with Sidebar and inspection drawers.

**Rationale**: Fixed 260 plus 340 pixel side columns currently compress the chat at common laptop widths.

**Alternatives considered**: A single 720 pixel breakpoint causes abrupt reflow and inaccessible intermediate widths.

## Icons

**Decision**: Add a small local SVG React module covering only icons required by touched controls.

**Rationale**: It improves consistency without a new dependency, license review, or vendor chunk.

**Alternatives considered**: Unicode glyphs vary by platform. A general icon package triggers the dependency approval gate.

## Settings decomposition

**Decision**: Keep CapabilitySettingsView as the public orchestrator and move each category into a private focused component sharing layout and async-state helpers.

**Rationale**: The current file duplicates busy, problem, refresh, form, and list behavior across six categories.

**Alternatives considered**: Leaving the file intact makes visual and accessibility fixes diverge. A generic schema-driven form would be speculative abstraction.

## Browser and Desktop validation

**Decision**: Keep automated Vitest, strict typecheck, Vite build, and Desktop consumer gates. Add manual real-browser acceptance at representative viewports and document visual evidence; do not add Playwright in 080.

**Rationale**: Real layout cannot be proven by jsdom, but a browser dependency is outside the approved boundary.

**Alternatives considered**: Adding browser automation now violates the no-new-dependency constraint. Skipping browser acceptance would not validate the visual goal.
