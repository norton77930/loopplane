# Validation Quickstart: Web Frontend Visual Refactor

## Prerequisites

- Existing 076 worktree state is preserved.
- No backend, generated API, event, checkpoint, gateway, dependency, or lockfile changes are expected.
- Run commands from the repository root unless a working directory is shown.

## Automated gates

## Execution log

### Baseline before 080 implementation — 2026-07-13

- Web npm test: 44 files, 141 tests passed.
- Desktop npm test: 3 files, 10 tests passed.
- Existing uncommitted 076 work was preserved in the current checkout.

### Shell and conversation workspace slice — 2026-07-13

- Web npm run typecheck: passed.
- Web npm test: 47 files, 150 tests passed.
- Web npm run build: passed; 527 modules transformed.
- Desktop npm run typecheck: passed.
- Desktop npm test: 3 files, 12 tests passed.
- Targeted red-green coverage added for AppShell state, semantic icons, Sidebar navigation,
  integrated Composer, controlled attachment clearing, upload-clear races, navigation toggle,
  active-session model truthfulness, and Desktop shared dialogs.
- The local dev server accepted connections on 127.0.0.1:4173, but the in-app browser
  connection timed out after 30 seconds. The server and its child process were stopped.
  The manual viewport and visual matrix remains pending and is not counted as passed.

### Conversation hierarchy and Settings/inspection slice — 2026-07-13

- Web npm run typecheck: passed.
- Web npm test: 47 files, 159 tests passed.
- Web npm run build: passed; 528 modules transformed.
- Desktop npm run typecheck: passed after the shared MessageList hierarchy change.
- Desktop npm test: 3 files, 12 tests passed after the shared MessageList hierarchy change.
- Two read-only code-review rounds reported no Critical findings. Important findings for
  multi-file upload clearing, pending-upload submission, overlay dismissal, mobile drawer
  focusability, conversation scroll preservation, and Settings status truthfulness were
  reproduced with failing tests, fixed, and included in the passing gates above.
- Full-page Settings now has vertical category navigation, a localized return action, and
  preserved draft and conversation scroll state. Inspection has adaptive dismissal and
  distinct loading, empty, and error states.
- At this checkpoint, Settings category extraction under components/settings remained pending;
  the final acceptance record below supersedes that intermediate state.

### Web focused cycle

Working directory: apps/web

1. Run the focused test file for the component being changed.
2. Run npm run typecheck.
3. Run npm test.
4. Run npm run build.

Expected: all commands exit zero without new warnings.

### Desktop consumer gate

Working directory: apps/desktop

1. Run npm run typecheck.
2. Run npm test.

Expected: unchanged Web imports compile and shared message/dialog interactions pass.

## Manual browser matrix

Validate at 375, 768, 1024, and 1440 CSS-pixel widths:

- login, invalid token, and logout
- empty chat and example prompt
- session selection, search, star, rename, delete, and bulk selection
- long message, long code block, reasoning, tool success/failure, approval, question, termination, and retry
- model preference and active-session model label
- attachment upload success, failure, removal, and post-submit clearing
- full-page Settings and every category
- inline and overlay inspection with every category
- light and dark theme
- English and Traditional Chinese

At each width verify no horizontal page overflow, clipped action, unreachable drawer, or chat column below the specified minimum.

## Accessibility matrix

- Complete primary flows with keyboard only.
- Verify visible focus, Escape behavior, dialog focus trap, and focus return.
- Test 200% zoom.
- Enable reduced motion.
- Confirm loading and streaming announcements do not replay the whole conversation.
- Confirm selected locale updates document language.

### Settings extraction, accessibility, and final acceptance - 2026-07-13

- The six Settings categories are private modules under `apps/web/src/components/settings/`;
  `CapabilitySettingsView` remains the thin status and category orchestrator. Category render,
  draft/update, save/error callback, and state-preservation regressions are covered.
- Keyboard acceptance covers vertical and horizontal roving tabs, mobile navigation and
  inspection dialog traps, Escape dismissal, stable focus return across inline/overlay viewport
  transitions, and return from Settings to the chat Settings trigger.
- English and Traditional Chinese inspection/navigation/theme chrome is localized and the active
  locale synchronizes `document.documentElement.lang`.
- Conversation progress uses one polite non-atomic log owner, header/loading progress uses polite
  atomic status regions, and errors retain alert semantics. The termination marker is not a nested
  live region, preventing duplicate completion announcements.
- Focus-visible, reduced-motion, forced-color, 200/400-percent-equivalent reflow, and page-level
  horizontal-overflow contracts have focused automated coverage.

Final automated gates:

- Web `pnpm run typecheck`: passed.
- Web `pnpm test`: 50 files, 167 tests passed.
- Web `pnpm run build`: passed; 535 modules transformed.
- Desktop `pnpm run typecheck`: passed.
- Desktop `pnpm test`: 3 files, 12 tests passed.
- Final independent read-only review: no Critical findings; two Important focus/live-region
  findings were fixed, covered by regressions, and re-reviewed with no remaining Critical or
  Important findings.

Real Chromium acceptance used the already cached Playwright runtime without adding a project
dependency or changing a manifest/lockfile. Frontend HTTP boundaries were deterministically
intercepted so the matrix validates presentation states without requiring or modifying backend
services.

| Chromium viewport | Classification | Locales | Covered states | Result |
| --- | --- | --- | --- | --- |
| 1440 x 900 | wide desktop, inline inspection | en, zh-TW | chat, six Settings categories, inspection, error | pass |
| 1024 x 768 | desktop, overlay inspection | en, zh-TW | chat, six Settings categories, inspection, error | pass |
| 768 x 1024 | tablet | en, zh-TW | chat, six Settings categories, inspection, error | pass |
| 375 x 812 | mobile | en, zh-TW | chat, six Settings categories, inspection, error | pass |
| 640 x 900 | 200% reflow equivalent from a 1280 CSS-pixel basis | en, zh-TW | chat, six Settings categories, inspection, error | pass |
| 320 x 800 | 400% reflow equivalent from a 1280 CSS-pixel basis | en, zh-TW | chat, six Settings categories, inspection, error | pass |

- Chromium 149.0.7827.55 produced 110 ignored screenshots and 110 recorded state/reflow checks
  with zero failures. Light theme covered the complete matrix; dark theme plus reduced motion was
  additionally verified at the 1440 and 375 extremes.
- Every matrix state checked document/body horizontal overflow; overlay sizes also exercised
  Escape and focus return. The 640/320 viewports record the explicit 1280/2 and 1280/4 reflow
  method rather than claiming browser-UI zoom controls were automated.
- Binary screenshots and `report.json` are under the ignored
  `.playwright-mcp/spec080-visual/` test-artifact directory and are not tracked.
- Limitation: the in-app browser connection timed out at both 30 and 60 seconds, and the local
  image-preview bridge also timed out. No embedded-browser or manual screenshot-inspection claim
  is made; the standalone Playwright Chromium interactions, screenshots, DOM/accessibility
  assertions, and overflow checks completed successfully.

Final scope and public-safety review:

- `git diff --check` passed for the Web, Desktop consumer, and Spec 080 scope.
- The ignored-artifact check confirmed `.playwright-mcp/` remains excluded from version control.
- The scoped sensitive-string scan found no credentials, tokens, private hostnames, private paths,
  or copied reference content; its only generic match was the expected CSS password-input selector.
- No project dependency, manifest, lockfile, backend, public API, default, event/checkpoint, or
  gateway change was introduced by this continuation. Pre-existing user work remained intact.
- Rollback remains presentation-only: revert the Spec 080 Web changes and focused Desktop consumer
  tests; no data migration or backend rollback is required.

## Rollback

080 is presentation-only. Roll back by reverting the 080 changes under apps/web plus the focused Desktop consumer tests. Existing API, runtime, storage, event, and checkpoint data require no rollback or migration.

## Public-safety review

Review every changed file for credentials, tokens, private hostnames, internal paths, private project names, or copied reference content. Do not inspect or modify openspec.
