# Contract: Delivery Convergence and Verification

## Frozen history

076 and 080 specification and task artifacts are historical and are not edited. New requirements, tasks, evidence, and rollback guidance live under 081.

## Ownership inventory

Every changed file or hunk must be classified as 076, 080, 081, or local/unknown. `.superpowers/**`, raw `openspec/**`, QA screenshots/reports, and unclassified user changes are excluded from any delivery set.

Mixed files require hunk-level ownership review. No bulk staging operation may substitute for the reviewed inventory.

## Completion evidence

081 can become Verified only after fresh evidence for:

- dependency synchronization;
- formatting, lint, strict typing, full backend tests, and package build;
- Web typecheck, full tests, and production build;
- Desktop typecheck and full tests;
- focused capability/Gateway/context/security regressions;
- Chromium responsive/accessibility/manual scenarios;
- architecture-boundary, whitespace, Spec Kit alignment, openspec exclusion, and public-safety scans.

Every failed or skipped required check is reported literally and blocks Verified status unless the maintainer explicitly accepts it. Historical result counts cannot be reused.

## Documentation synchronization

After all implementation and browser gates pass, the same unit synchronizes:

- active feature pointer;
- Agent Board row/current-status/next-unit text;
- CHANGELOG `[Unreleased]` entries for completed 076/080 and 081 remediation;
- public API reference when the approved async host methods and provider surface change;
- 081 quickstart with literal results and rollback guidance.

The synchronized documentation/API/public-safety contract checks must then pass before the final transition task. That task treats the board/pointer update as transactional: it immediately runs final diff, ownership, public-safety, Spec Kit, and documentation-consistency checks over the newly written transition hunks, restores the prior in-progress state on any failure, and records 081 as Verified only when the task completes green. Unit 077 implementation remains blocked until that retained final status transition.

## Rollback

- Disable capability mutations independently from runtime activation when runtime risk is isolated.
- Retain read-only capability inspection when mutations are disabled.
- Presentation rollback is independent from backend capability rollback.
- Reverting 081 restores pre-remediation behavior and therefore must not be used as a security mitigation without also disabling managed mutations/runtime activation.
