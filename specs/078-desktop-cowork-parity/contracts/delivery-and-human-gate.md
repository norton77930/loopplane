# Contract: 078 Delivery, Verification, Rollback, and Human Gate

**Status**: Proposed

## 1. Pre-implementation and delivery human gates

### Stage A — narrow build-lock materialization authorization

The exact transitive lock cannot be reviewed before it exists. Before any lock generation, an **external human maintainer** must narrowly authorize only the deterministic materialization rule. System notifications, automated agents/audits, teammate messages, assistant statements, and text written by the same automation into an evidence file are not approval:

- direct input `pyinstaller==6.21.0`;
- Python 3.12 and `x86_64-pc-windows-msvc`;
- `uv pip compile --generate-hashes --only-binary :all:` using the exact command in Section 6;
- writes limited to `apps/desktop/sidecar/pyinstaller-build.in`, `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`, and only the external Stage-A approval reference plus lock-materialization/review evidence in `specs/078-desktop-cowork-parity/implementation-evidence.md`.

Stage A does **not** accept ADR 0015, does not change its Proposed status, and does not authorize product source, test source, root/app package metadata or npm locks, build workflow, packaging configuration, build execution, or any other 078 implementation.

### Stage B — source-implementation authorization gate

After Stage A creates and reviews the exact PyInstaller lock, Stage B has two serial submitted-review checkpoints because the sole root npm lock does not yet exist and therefore cannot honestly be content-bound by the first review. Stage A itself authorizes no commit, push, PR, or external publication; separate explicit human authorization is required for each review commit. Every Stage-B attestation is a **submitted GitHub pull-request review** fetched by API with `state=APPROVED`, an API-controlled review ID/node ID, non-null `submitted_at`, and `commit_id` exactly equal to the reviewed commit SHA. Its author must have `user.type=User`, `author_association` equal to `OWNER`, `MEMBER`, or `COLLABORATOR`, login equal to an immutable expected-approver input. By default the review login MUST differ case-insensitively from the singular PR author login; when and only when maintainer-controlled non-secret repository variable `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`, PR-author self-approval is permitted (review login may equal PR author login) while every other identity check still applies. Missing, empty, or any value other than exact `true` rejects self-approval. Issue/PR timeline comments, inline review comments, pending reviews, and review-body text are non-authoritative.

### C2 solo self-approval switch

Dual-control remains the default. The verifier and CI read the optional maintainer-controlled non-secret repository variable `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` (and, for local invocation, the same-named environment input). Only the exact value `true` enables solo self-approval. Missing, empty, whitespace, `True`, `1`, `yes`, or any other value MUST leave dual-control enabled and reject PR-author self-approval.

When dual-control is enabled, each review login MUST equal the immutable expected-approver login and MUST differ case-insensitively from the singular PR author login. When solo self-approval is enabled, each review login MUST still equal the expected-approver login and MAY equal the PR author login; bots, non-User actors, non-OWNER/MEMBER/COLLABORATOR association, comments, pending/inline reviews, and review-body text remain non-authoritative. The switch MUST NOT be discovered from ADR text, evidence files, mutable refs, or list/search APIs.

### GitHub authority and credential seam

The verifier receives repository owner, repository name, pull-request number, expected approver login, optional C2 self-approval switch, mode, and mode-specific immutable review locator tuples. Bootstrap mode receives the T002 review ID and expected commit SHA. Final mode receives both the T002 bootstrap and T005 final review IDs/expected commit SHAs. Delivery mode receives all three T002/T005/T090 review IDs/expected commit SHAs. The shared repository/PR/expected-approver inputs plus each review/commit pair form one complete locator; all reviews MUST belong to that exact PR, and the IDs MUST be pairwise distinct where more than one is supplied. No prior locator may be discovered from ADR/evidence text, repository files, mutable refs, or list/search APIs. For the submitted-review CI route, the T090 ID/commit comes from the event and must match API data; the T002/T005 IDs and commit SHAs come only from maintainer-controlled non-secret repository variables `LOOPPLANE_DESKTOP_BOOTSTRAP_REVIEW_ID`, `LOOPPLANE_DESKTOP_BOOTSTRAP_COMMIT_SHA`, `LOOPPLANE_DESKTOP_FINAL_REVIEW_ID`, and `LOOPPLANE_DESKTOP_FINAL_COMMIT_SHA`, while `LOOPPLANE_DESKTOP_EXPECTED_APPROVER` supplies the expected login and optional `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` (exact `true` only) supplies the solo self-approval switch.

The verifier's only credential source is a non-empty short-lived `LOOPPLANE_STAGE_B_GITHUB_TOKEN` environment variable injected into an isolated verifier process/step. The token MUST NOT be accepted on the command line, from an evidence/config file, or through `GH_TOKEN`, `GITHUB_TOKEN`, `gh auth`, git credential helpers, persisted browser/login state, or another ambient fallback. The verifier emits only a bounded non-secret descriptor. After it exits, the calling environment MUST remove the named token and all ambient GitHub credential variables before invoking any wrapper or external build command. GitHub Actions must declare only `contents: read` and `pull-requests: read`, map `${{ github.token }}` to the named variable only for the verifier step, run package/freeze/smoke in a separate token-free step, and never use `pull_request_target` to bypass fork trust or permission failures.

The verifier uses `Authorization: Bearer <redacted>`, `Accept: application/vnd.github+json`, and `X-GitHub-Api-Version: 2022-11-28` with redirects disabled, a 15-second deadline per request, a 60-second total verifier deadline, and at most one retry for a transport failure or `502`/`503`/`504`; authentication/authorization/not-found/rate-limit failures are never retried. Authority comes only from these REST resources:

1. `GET /repos/{owner}/{repo}/pulls/{pull_number}` for the exact pull request identity and `user.login` author;
2. `GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}` for `id`, `node_id`, `state`, `submitted_at`, `commit_id`, `user.login`, `user.type`, and `author_association`;
3. `GET /repos/{owner}/{repo}/git/commits/{commit_id}` for the exact tree SHA;
4. `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1` for the complete inventory and app-local-lock absence, with `truncated=false` required; and
5. `GET /repos/{owner}/{repo}/git/blobs/{sha}` for exact bound-file bytes.

No list/search endpoint, pagination result, mutable PR-head ref, checkout content, or editable evidence text may establish authority. The review login must exactly match the immutable expected-approver login. By default the review login MUST differ case-insensitively from the singular PR author login; when and only when maintainer-controlled non-secret repository variable `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`, PR-author self-approval is permitted (review login may equal PR author login) while every other identity check still applies. Missing, empty, or any value other than exact `true` rejects self-approval. Final mode MUST refetch both the T002 and T005 singular review/commit/complete-tree/blob authorities from their immutable locators. It computes an exact full-tree diff from the T002 reviewed tree to the T005 reviewed tree over path, entry type, Git mode, blob SHA, additions, modifications, and deletions. The only permitted additions/modifications are regular blobs at `tests/contract/test_desktop_delivery_gate.py`, `scripts/verify-desktop-stage-b.ps1`, `package.json`, `package-lock.json`, `apps/web/package.json`, `apps/desktop/package.json`, `packages/cowork-presentation/package.json`, and the bounded Stage-B-bootstrap record in `specs/078-desktop-cowork-parity/implementation-evidence.md`; the only permitted deletions are `apps/web/package-lock.json` and `apps/desktop/package-lock.json`. Every allowed addition must be a `100644` regular blob, every allowed modification must retain its T002 regular-blob mode, and no type/mode-only change is permitted. The evidence-file delta is accepted only after normalizing the exact bounded bootstrap block and proving every populated value against the refetched T002 authority. Any other path/type/mode/blob/deletion difference—including `src/**`, workflow, product source, ADR/design, test outside the one verifier test, symlink, or gitlink change—fails closed before T005 acceptance.

Delivery mode MUST refetch T002, T005, and T090 independently from the three immutable locators, rerun the exact T002-to-T005 full-tree allowlist diff, rederive every prior tree/bundle/lock identity from API bytes rather than records, prove all three review IDs pairwise distinct, and then bind the T090 delivery tree. Missing/empty credentials, insufficient repository access, `401`, `403`, `404`, `429`, exhausted rate limit, redirect, timeout, malformed JSON, unexpected API shape, missing required field, pagination dependence, `truncated=true`, actor-association failure, expected-login mismatch, unauthorized PR-author self-approval when `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is not exactly `true`, stale/replayed/substituted prior locator, commit mismatch, full-tree-diff violation, or blob/tree mismatch fails closed: no descriptor is emitted, no accepted-input directory is authoritative, no ADR/evidence acceptance field is written, and no sync/build proceeds. Diagnostics contain only a bounded public-safe failure enum plus HTTP status/request class; token values, authorization headers, cookies, query credentials, and raw response bodies never enter logs, exceptions, evidence, artifacts, or snapshots.

**Stage B bootstrap review (T002)** binds the design, Python dependency authority, and Stage-A PyInstaller lock but authorizes only T003 and T004. ADR 0015 remains `Proposed`. T003 may write and observe only the focused RED delivery-verifier tests. T004 may then implement `scripts/verify-desktop-stage-b.ps1` and materialize the complete final package-manifest graph needed for final review: root `package.json`; `apps/web/package.json`; `apps/desktop/package.json`; `packages/cowork-presentation/package.json`; every final workspace/dependency/script/`main`/exports/files/package field that later build tasks consume; the sole root `package-lock.json` generated only after those four manifests are final; and removal of the two app-local locks. T004 may reference later-created source/build scripts but may not install dependencies, build, add presentation source, modify workflow, or begin other product implementation. After T005 accepts these bytes, T006+ must treat all four manifests and the root lock as immutable; any required manifest/lock edit returns to T004 and requires a new T005 final submitted review before sync/build. The bootstrap bundle contains sorted relative paths plus SHA-256 for `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`, both checklists, all five contracts, the complete Proposed ADR, `pyproject.toml`, `uv.lock`, `pyinstaller-build.in`, and the candidate PyInstaller transitive lock. T002 also records the refetched bootstrap review ID, commit SHA, tree SHA, complete non-truncated path/type/mode/blob inventory digest, bundle digest, and PyInstaller-lock digest in the bounded Stage-B-bootstrap portion of `implementation-evidence.md`; the later verifier treats those fields only as comparison output, never as locator or authority, and rederives them from the immutable T002 invocation tuple. That record is not final implementation authority and cannot change ADR status.

**Final Stage B review (T005)** uses a new submitted review ID and a new exact commit after T004. Its pre-implementation canonical bundle contains every bootstrap-bundle path plus `tests/contract/test_desktop_delivery_gate.py`, `scripts/verify-desktop-stage-b.ps1`, complete final root/Web/Desktop/shared package manifests—including every dependency/workspace/script/entrypoint/exports/files field consumed later—the sole root `package-lock.json`, and explicit absence records for `apps/web/package-lock.json` and `apps/desktop/package-lock.json`. It therefore binds both accepted dependency authorities before any shared-source, workflow/build implementation, or product source change. The final review accepts the architecture and delivery contracts—not not-yet-created implementation bytes—including:

- ADR 0015;
- [Desktop stdio RPC V1](desktop-rpc-v1.md);
- [Desktop IPC and Shared Presentation Boundary](desktop-ipc-and-presentation.md);
- [Desktop Profile, Workspace, Resume, and Turn Audit](desktop-profile-workspace-and-audit.md);
- [Portable Desktop Backup and Restore V1](backup-and-restore.md);
- this delivery/rollback contract;
- the Stage-B-bound `pyproject.toml`/`uv.lock` production runtime graph and the exact Desktop extras allowlist;
- the generated `pyinstaller-build-windows-py312.txt`, its recorded SHA-256, and the specified sealed-input install/build mechanism;
- the deterministic JavaScript clean-install/shared-source graph with complete final root/Web/Desktop/shared manifest metadata, one exact root lock, both app-local locks absent, and no later manifest/lock mutation before package build;
- the unencrypted authorized-content backup disclosure and all excluded scope;
- the specified proof-before-Host validator, publication, platform-durability, ambiguous-proof, stale-binding, dual-slot recovery, and post-swap proof invariants.

T005 final mode must receive both immutable T002 and T005 locator tuples, refetch and validate both submitted reviews plus the singular PR/commits/complete trees/blobs, and rederive the bootstrap inventory/bundle/lock identities independently of evidence. It validates the final review's canonical API URL, numeric ID, node ID, non-null exact RFC 3339 `submitted_at`, live `APPROVED` state, expected authorized human actor (default dual-control: distinct from the PR author; solo self-approval only when `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`), and exact `commit_id`; enforces distinct T002/T005 IDs; and accepts the final tree only when the exact full-tree diff from T002 is limited to the T003/T004 allowlist defined above. It then derives the canonical final bundle, PyInstaller-lock digest, and root-lock digest from the content-addressed T005 commit; compares all current bound artifacts while allowing only later ADR Status/acceptance-block normalization; and rejects any mismatch. Only after success may T005 change ADR 0015 from `Proposed` to `Accepted` and populate the bounded acceptance blocks in ADR/evidence. Each file must contain exactly one identical machine-readable line for each key: `Stage B Approval API URL:`, `Stage B Approval ID:`, `Stage B Approval Node ID:`, `Stage B Approval Submitted At:`, `Stage B Approver Login:`, `Stage B Reviewed Commit SHA:`, `Stage B Reviewed Tree SHA:`, `Stage B Review Bundle SHA-256:`, `Accepted PyInstaller lock SHA-256:`, and `Accepted Root package-lock SHA-256:`. Final-mode verification ignores editable review-body content and normalizes only the ADR exact Status value plus bounded acceptance blocks. A missing/dismissed review, stale/substituted locator, expected-actor/PR-author/`commit_id` mismatch, reused review ID, full-tree-diff violation, bound-artifact drift, root-lock drift, or reappearance of either app-local lock requires a new final submitted approval review. The evidence file cannot authorize itself.

No T006+ product work may begin until T005 final verification and ADR acceptance succeed. Final Stage B then authorizes only local source/tests/docs/build-configuration/workflow changes required by 078 while the accepted authority verifier, root/Web/Desktop/shared manifests, and sole root lock remain immutable. Any package metadata or lock change requires a new final submitted review before install/build. It does **not** authorize:

- a new runtime dependency or optional extra;
- Event Bus/runtime-event schema changes;
- checkpoint record/schema changes;
- Gateway SPI/stage/invocation-path changes;
- runtime default changes;
- Web `/v1`, SSE/WS, generated client, or other outward contract changes;
- local HTTP server, remote control, CLI parity, distributed/multi-user execution;
- version bump, release, signing, notarization, publishing, deployment, commit, branch, tag, or pull request.

### Stage C — post-implementation delivery-execution gate

T005 authorizes implementation but does not attest to future wrapper, workflow, smoke, or product-source bytes and does not authorize the first sidecar freeze, `electron-builder` package, or packaged-artifact smoke. After T006–T089 source work and source-only regression gates are complete, T090 requires a third submitted GitHub PR review over one exact implementation commit. Its review ID must differ from both T002 and T005, its expected approver must satisfy the same non-bot association checks and the C2 self-approval rule (`LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` exact `true` permits PR-author equality; otherwise PR-author separation is required), and no repository write may be inferred from the review itself.

Delivery mode binds the accepted T005 design/dependency authorities without changing ADR status and derives a canonical delivery bundle over the complete non-truncated reviewed tree entries that can determine the artifact or smoke: root/Python authorities; `src/loopplane/**`; `apps/desktop/**` excluding declared untracked build outputs; shared-presentation and Web source required by Desktop; `tests/**`; the four delivery scripts; `.github/workflows/desktop.yml`; ADR 0015; and all 078 contracts/tasks. It requires the accepted manifests/root lock to be byte-identical to T005, both app-local locks absent, the exact six Python extras unchanged, and actual verifier/wrapper/workflow/PyInstaller-spec/Electron packaging/accessibility/UI-Automation smoke implementation present.

Delivery mode is invoked with all three immutable T002/T005/T090 locator tuples. It independently refetches every singular review/commit/complete-tree/blob authority, re-proves the same PR and expected-approver identity under the C2 self-approval rule for each review, proves pairwise-distinct IDs, reruns the exact T002-to-T005 allowlist diff, rederives the T002/T005 bundles and accepted lock digests without trusting ADR/evidence, and only then verifies the T090 delivery tree. After successful delivery-review verification, delivery mode writes no ADR field. It emits a bounded non-secret descriptor containing all three verified review/commit/tree/bundle identities plus accepted lock digests and may append exactly one delivery field set to `implementation-evidence.md`: `Delivery Approval API URL:`, `Delivery Approval ID:`, `Delivery Approval Node ID:`, `Delivery Approval Submitted At:`, `Delivery Approver Login:`, `Delivery Reviewed Commit SHA:`, `Delivery Reviewed Tree SHA:`, `Delivery Review Bundle SHA-256:`, `Delivery Accepted PyInstaller lock SHA-256:`, and `Delivery Accepted Root package-lock SHA-256:`. The delivery review and field set are distinct from T005's architecture acceptance and cannot replace the three invocation locators.

The verifier materializes a fresh no-link source snapshot from the exact reviewed commit, never from mutable worktree bytes: after the API has established the commit/tree inventory, it reads each required regular blob by exact SHA from the local Git object database through non-interactive `git cat-file --batch`, recomputes its Git blob identity, and writes only matching reviewed-tree paths before marking the snapshot read-only. Missing objects, symlink/gitlink/tree-mode surprises, path collisions, or blob mismatches fail closed; this materialization route accepts no credential and performs no network fetch. The verifier then exits and the tokenized environment is destroyed or explicitly scrubbed. The package wrapper and sidecar wrapper accept only the descriptor plus its delivery-source and accepted-dependency snapshot paths; they MUST reject execution if `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` is present and MUST launch `npm`, lifecycle scripts, `uv`, PyInstaller, electron-builder, the sidecar wrapper, and every descendant with those variables removed. Current checkout source is comparison input only. The first package execution is therefore a token-free rerun on the same reviewed commit after approval. The T088 workflow may exist and run source checks before Stage C, but its package/freeze/smoke path must fail closed until the delivery review exists; `pull_request_target` remains prohibited. Any delivery-review dismissal, stale/substituted prior locator, expected-actor/PR-author/commit/tree/bundle/source-snapshot mismatch, T002-to-T005 diff violation, T005 authority drift, app-lock reappearance, post-review determinant change, or credential-bearing build environment requires a new applicable review or corrected token-free invocation before freeze/package/smoke.

If implementation discovers that any excluded change is required, that slice stops and returns to a separate ADR/human gate.

## 2. Planned implementation waves and revert boundaries

### Wave 1 — Host resumed-interaction facade

Scope:

- additive `LoopPlaneHost.resume_session(...)` context manager;
- additive optional `working_scope` in controller resume with `None` preserving current behavior;
- focused Host lifecycle, principal, resume, default-preservation tests and public docs.

Must remain independently revertible without Desktop UI/protocol changes.

### Wave 2 — Python sidecar protocol/profile core

Scope:

- first build bounded Desktop RPC V1 dispatcher/writer state as pure injected non-executable code, without changing the launchable raw `{op}` bridge or constructing Host/store/profile state;
- implement/export the public non-instance active-generation validator plus canonical-root OS-backed Profile Ownership Lock/bootstrap gate, with aliased-root/second-process `busy` and zero Host, kernel crash release, and unsupported/remote/ambiguous fail-closed behavior; only after that gate is green may the executable bridge be replaced and wired to the dispatcher, so no intermediate launchable state reaches Host before ownership/recovery validation; Host-only session registry and inner interaction lease;
- Desktop profile/generation, portable Projects, Host-owned session star actions, private workspace binding, SQLite opt-in, audit adapter, transient-draft exclusion, and all-writer Profile Mutation Lease primitives;
- before the first Host is constructed: platform-scoped initial publication (POSIX file/directory/both-parent `fsync` physical-power-loss scope; Windows supported-volume regular-file flush/write-through move/reopen process-crash scope), canonical immutable publication receipt declaring pristine checkpoint/artifact `absent_uninitialized`, absence validation without sidecar store creation, first-normal-Host store ownership, receipt-bound bootstrap proof before exact pointer, current mutable-generation validation, and pointer/proof/receipt/journal recovery with unexpected payloads or unsupported/mismatched states failing locked at zero Host;
- protocol, bootstrap/power-fault/profile, project/star, workspace, draft-exclusion, public-safety tests.

Must not import controller/checkpoint private implementation into sidecar.

### Wave 3 — Electron main/preload/client boundary

Scope:

- child process/RPC supervisor and strict framing;
- sender-validated per-operation IPC for every named app/session/Project/interaction/inspection/audit/agent-control/capability/workspace/backup/restore operation;
- frozen typed preload/global facade, exhaustive one-to-one public recovery mapping, and subscription cleanup;
- Desktop client adapters and crash/version diagnostics;
- test-first Electron main/preload/global-typing/client ownership for the complete facade, including non-interaction reads/mutations and native picker cancellation/path privacy.

Must remove, not retain alongside, the raw `sidecar:send`/`sidecar:line` escape hatch.

### Wave 4 — Shared presentation and cowork shell

Scope:

- narrow transport-neutral presentation host;
- Web adapter preserving current Web behavior;
- Desktop adapter and thin composition root;
- multi-pane, single-active, sidebar, keyboard/focus, history/fork/settings/inspection flows;
- Web/Desktop UI regression and accessibility tests.

Must not make Web import Electron/Desktop runtime or Desktop pretend to be HTTP.

### Wave 5 — Audit/backup/restore

Scope:

- additive read-only Host turn-audit projection;
- additive default-unavailable Host portable snapshot export and dedicated read-only staged-validation facades backed by an explicitly injected Desktop provider;
- allowlisted archive/manifest/integrity implementation;
- disclosure and native destination/source flows;
- Host-owned consistent SQLite snapshot and provenance-eligible checkpoint-referenced Gateway artifacts;
- one all-writer Profile Mutation Lease: backup owns it before Host snapshot/profile serialization through archive finalization; restore reserves it before staging through commit/cancel/expiry/shutdown cleanup; every competing session/interaction/Project/workspace/capability/profile/backup/restore writer—including persisted `workspace.revalidate`—is rejected before dispatch, with only owning restore transitions and bounded no-new-work teardown allowed;
- exhaustive backup/restore internal-cause mapping to existing RPC code/category/retryability/required-or-absent recovery and fixed `messageKey`, with no cause-label leakage;
- one reusable fail-closed platform-scoped generation-publication primitive: POSIX regular-file/bottom-up-directory/both-parent `fsync` plus rename under the physical-power-loss claim; Windows supported-local-volume regular-file `FlushFileBuffers`, write-through move/replace, and reopen/current validation under process/application-crash consistency; canonical immutable publication receipt; unsupported/error pre-pointer handling; no undocumented Windows directory-flush claim;
- two complete checksummed COW Restore Journal slots with exact previous proof/pointer preimages and candidate receipt, candidate proof after runtime-owner swap, exact startup rollback/fail-lock, proof post-effect/pre-acknowledgement freeze-and-restart adjudication, mutable-generation restart validation, and stale `relink_required` binding pre-lookup denial/cleanup ordering;
- security/recovery/property-style tests with synthetic content markers, drafts, Host I/O sentinels, identical-ID device-binding revival sentinels, POSIX and Windows platform fault matrices, current mutable-state restart, every pointer/proof/journal write boundary including post-effect/pre-ack proof failure, single-slot recovery, both-slot fail-lock, and cleanup interruption.

Must remain revertible without affecting existing runtime checkpoint schema.

### Wave 6 — Packaging, CI, documentation, and board transition

Scope:

- PyInstaller 6.21.0 input plus a reviewed Windows/Python-3.12 complete transitive hash lock, Stage-B-bound `pyproject.toml`/`uv.lock`, and the exact six-extra packaged runtime graph, consumed only from verifier-materialized accepted snapshots through `scripts/build-desktop-sidecar.ps1`; all bare-PATH/global-PyInstaller package and documentation routes are removed;
- deterministic renderer/main/preload/sidecar build graph and final-Stage-B-bound sole root npm lock with both app-local locks removed, consumed only inside the isolated `scripts/build-desktop-package.ps1` source/dependency snapshot;
- `electron-builder` alignment and the exact external-CWD `smoke-desktop-artifact.ps1` artifact-smoke CLI, with packaged-smoke-only accessibility enablement and actual packaged-tree proof of the fixed Name/ControlType locator pairs rather than AutomationId assumptions;
- a required Windows x64 packaging/artifact-smoke CI job on `windows-latest` or an approved GUI-capable Windows 11 runner, with `contents: read`/`pull-requests: read`, token injection limited to the isolated verifier step, separate token-free wrapper/build/smoke execution, no `pull_request_target`, and trigger coverage for every root lock/shared/Host/Desktop/Web/test/script/ADR/evidence input rather than the legacy Linux/apps-only filter;
- docs/CHANGELOG/capabilities/gap/architecture snapshots, including replacement of legacy direct `pip install pyinstaller` instructions;
- board 078 transition only after all evidence passes.

Release/signing remain excluded.

## 3. Exact critical files expected

Implementation may refine paths while preserving boundaries. Expected high-value files:

```text
src/loopplane/host/host.py
src/loopplane/host/audit.py
src/loopplane/host/snapshot.py
src/loopplane/controller/controller.py
src/loopplane/host/config.py
src/loopplane/checkpoint/*                  # read projection/testing only; no record schema change

tests/contract/test_desktop_boundary.py
tests/contract/test_desktop_rpc_v1.py
tests/contract/test_desktop_public_safety.py
tests/unit/test_host_turn_audit.py
tests/unit/test_host_portable_snapshot.py
tests/unit/test_desktop_profile.py
tests/unit/test_desktop_workspace.py
tests/unit/test_desktop_backup.py
tests/unit/test_desktop_restore.py
tests/integration/test_host_session.py
tests/integration/test_host_durability.py
tests/integration/test_desktop_sidecar.py
tests/integration/test_desktop_profile.py
tests/integration/test_desktop_backup.py
tests/integration/test_desktop_restore.py

apps/desktop/sidecar/bridge.py
apps/desktop/sidecar/profile.py
apps/desktop/sidecar/durability.py
apps/desktop/sidecar/projects.py
apps/desktop/sidecar/runtime.py
apps/desktop/sidecar/backup.py
apps/desktop/sidecar/restore.py
apps/desktop/sidecar/pyinstaller-build.in
apps/desktop/sidecar/pyinstaller-build-windows-py312.txt
apps/desktop/sidecar/loopplane-sidecar.spec
scripts/verify-desktop-stage-b.ps1
scripts/build-desktop-sidecar.ps1
scripts/build-desktop-package.ps1
scripts/smoke-desktop-artifact.ps1
apps/desktop/electron/main.ts
apps/desktop/electron/preload.ts
apps/desktop/src/sidecar.ts
apps/desktop/src/App.tsx
apps/desktop/src/__tests__/**
apps/desktop/package.json
apps/desktop/tsconfig*.json
apps/desktop/vite.config.*
apps/desktop/electron-builder.yml

package.json
package-lock.json
apps/web/package.json
apps/web/package-lock.json                 # existing input; removed by accepted migration
apps/desktop/package-lock.json             # existing input; removed by accepted migration
packages/cowork-presentation/**

apps/web/src/App.tsx
apps/web/src/api/transport.ts
apps/web/src/state/chat.ts
apps/web/src/components/AppShell.tsx
apps/web/src/components/MessageList.tsx
apps/web/src/components/ApprovalDialog.tsx
apps/web/src/components/QuestionDialog.tsx
apps/web/src/components/InspectionPanel.tsx
apps/web/src/components/CapabilitySettingsView.tsx
apps/web/src/components/settings/AgentControlsSettings.tsx
apps/web/src/**/__tests__/**

.github/workflows/desktop.yml
docs/desktop-gui.md
docs/manual-qa.md
docs/web-frontend.md
docs/web-api-host.md
docs/api-reference.md                   # if Host public facade is documented here
docs/capabilities.md
docs/gap-analysis.md
docs/architecture/*dated audit/risk snapshots*
docs/loopplane-agent-board.md
CHANGELOG.md
```

Files under `.superpowers/**`, build outputs, logs, local profiles, archives, tokens, QA screenshots unless explicitly approved, or unrelated untracked files are never staged as 078 delivery.

## 4. Proposed clean-install JavaScript workspace strategy

The human-gate proposal is to replace the cross-app source alias with one first-party npm workspace graph:

```text
package.json                         # private root; npm workspaces only
package-lock.json                    # one authoritative lock for first-party JS workspaces
apps/web/package.json                # @loopplane/web app composition
apps/desktop/package.json            # @loopplane/desktop app composition
packages/cowork-presentation/
├── package.json                     # private @loopplane/cowork-presentation
├── src/                             # shared shell/chat/settings/inspection presentation
└── tsconfig.json
```

Rules:

- No new third-party package name is introduced by 078. Existing React/Markdown/highlight/test/build dependencies are declared at the workspace that imports them and captured by the one root lock.
- `@loopplane/cowork-presentation` is a private first-party workspace package, not a published/runtime-downloaded dependency.
- Web and Desktop import the shared package through npm workspace resolution; Desktop no longer compiles arbitrary `../web/src` through an alias or relies on `apps/web/node_modules`.
- `npm ci` at repository root is the clean-install source of truth for both apps. App scripts may be invoked with `npm --workspace` and CI may cache only from the root lock.
- Web remains the owner of HTTP/SSE/WS adapters and Desktop remains the owner of Electron/preload adapters. The shared workspace contains no Electron, FastAPI, HTTP auth, or sidecar process code.
- Migration of the two existing app lockfiles into one root lock is limited to this deterministic first-party build graph and requires review for dependency-version drift. It must not opportunistically upgrade unrelated packages. Once the root lock is proven, `apps/web/package-lock.json` and `apps/desktop/package-lock.json` are removed; `package-lock.json` is the only authoritative app/workspace lock and app-local install commands may not recreate divergent locks.

Proposed commands:

```powershell
npm ci
npm --workspace @loopplane/web run typecheck
npm --workspace @loopplane/web test -- --run
npm --workspace @loopplane/web run build
npm --workspace @loopplane/desktop run typecheck
npm --workspace @loopplane/desktop test -- --run
npm --workspace @loopplane/desktop run build
npm --workspace @loopplane/desktop run build:sidecar
npm --workspace @loopplane/desktop run dist
```

A different strategy requires a revised human-gate record and equivalent proof that each clean install resolves shared presentation dependencies without sibling checkout state.

## 5. TDD rule per wave

For each behavior slice:

1. add/adjust the smallest focused failing test;
2. observe the intended failure for the missing behavior;
3. implement the smallest boundary-preserving change;
4. run the focused test and adjacent regression tests;
5. review public-safety, default preservation, teardown, and revert boundary;
6. run the wave's broader gate before moving on.

No board/CHANGELOG completion claim precedes final verification.

## 6. Verification matrix

### Documentation/contract gates before source

- requirements checklist remains fully passing;
- implementation-readiness/architecture-security checklist is completed;
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, contracts, ADR, tasks, and analysis have no unresolved contradiction or `[NEEDS CLARIFICATION]`;
- every FR/SC maps to tasks and planned evidence;
- T002 verifies a submitted bootstrap review that binds the design/Python authorities/PyInstaller lock and authorizes only T003 RED tests plus T004 verifier/dependency-manifest/root-lock materialization while ADR 0015 remains Proposed. ADR 0015 becomes `Accepted` only after T005 verifies a distinct final submitted review whose exact API identity/actor/`commit_id` and commit-derived complete non-truncated tree/canonical bundle bind the PyInstaller lock, root/app/shared manifests, sole root lock, verifier/tests, and app-local-lock absence; ADR/evidence then contain one matching final field set including both accepted lock digests. Both modes use immutable invocation inputs, the sole explicit token environment seam, minimum read permissions, version-pinned singular REST resources, and fail-closed redacted credential/HTTP/rate/timeout/API handling. No T006+ work or install/build begins before T005.

### Python/architecture gates

```powershell
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q tests/contract/test_desktop_boundary.py tests/contract/test_desktop_rpc_v1.py tests/contract/test_desktop_public_safety.py tests/unit/test_host_turn_audit.py tests/unit/test_host_portable_snapshot.py tests/unit/test_desktop_profile.py tests/unit/test_desktop_workspace.py tests/unit/test_desktop_backup.py tests/unit/test_desktop_restore.py tests/integration/test_host_session.py tests/integration/test_host_durability.py tests/integration/test_desktop_sidecar.py tests/integration/test_desktop_profile.py tests/integration/test_desktop_backup.py tests/integration/test_desktop_restore.py
uv run pytest -q
uv build
```

Also run existing architecture/conformance tests that prove:

- only Gateway invokes tools;
- Event Bus/outbound seam ownership remains unchanged;
- tools/import boundaries remain intact;
- checkpoint record/schema and generated/public contract guards remain green;
- default Host/Web/CLI behavior remains unchanged.

The recorded pre-078 baseline is `1496 passed, 8 skipped, 1 warning`; final reporting must state actual fresh results rather than assume this baseline.

### Web gates

For source regression only, from a clean root first-party install state using the accepted workspace strategy (this checkout-root install is not SC-009 package-artifact evidence):

```powershell
npm ci
npm --workspace @loopplane/cowork-presentation run typecheck
npm --workspace @loopplane/cowork-presentation test -- --run
npm --workspace @loopplane/web run typecheck
npm --workspace @loopplane/web test -- --run
npm --workspace @loopplane/web run build
```

Expected baseline before 078: 57 test files / 192 Vitest tests. Final reporting uses fresh counts. T050/T094 execute the exact six-viewport/locale/theme/keyboard/reflow procedure in `quickstart.md` and write only ignored local results under `.playwright-mcp/spec078-desktop-cowork/`; baseline 79/79 is historical, not inherited evidence.

### Desktop source gates

```powershell
npm ci
npm --workspace @loopplane/desktop run typecheck
npm --workspace @loopplane/desktop test -- --run
npm --workspace @loopplane/desktop run build
```

The accepted build scripts must explicitly emit renderer, Electron main, and preload outputs. Expected source-test baseline before 078: 3 files / 12 Vitest tests; final reporting uses fresh counts.

### Required Windows packaging CI gate

The legacy `.github/workflows/desktop.yml` Linux/apps-only source gate is not packaging evidence; T082 must first establish failing delivery-route/workflow expectations and T088 must then replace it with the required job. The workflow declares `permissions: { contents: read, pull-requests: read }`; `${{ github.token }}` is mapped to `LOOPPLANE_STAGE_B_GITHUB_TOKEN` only for the isolated verifier/materialization step and is never persisted, logged, or uploaded. The immutable expected-approver parameter comes from maintainer-controlled non-secret repository variable `LOOPPLANE_DESKTOP_EXPECTED_APPROVER`; T002/T005 prior locators come only from `LOOPPLANE_DESKTOP_BOOTSTRAP_REVIEW_ID`, `LOOPPLANE_DESKTOP_BOOTSTRAP_COMMIT_SHA`, `LOOPPLANE_DESKTOP_FINAL_REVIEW_ID`, and `LOOPPLANE_DESKTOP_FINAL_COMMIT_SHA`. Missing/empty values fail closed. Fork PRs lacking authority fail closed; `pull_request_target` and ambient authentication are prohibited.

`push` and `pull_request` path-filtered runs execute source gates and prove the package route remains closed before Stage C. The first package execution is a separate `pull_request_review` `submitted` run: immutable owner/repository and PR number come from the event repository/PR identity, T090 review ID and expected commit come from `github.event.review.id`/`commit_id`, T002/T005 locators come from the four repository variables, and the expected approver comes only from its repository variable. These values locate authority but do not establish it. The isolated verifier step independently refetches the singular PR plus all three review/commit/complete-tree/blob resources, validates every review is `APPROVED`, proves same PR and pairwise-distinct IDs, reruns the exact T002-to-T005 full-tree allowlist, rejects event/API disagreement, and emits only the bounded descriptor. The run uses the repository's existing `actions/checkout@v4` with `ref: ${{ github.event.review.commit_id }}`, `persist-credentials: false`, and sufficient object depth to make that exact commit's blobs available; it does not execute package source before delivery verification and materializes reviewed blobs through delivery mode. The checkout action may use the platform token without mapping it into later environments. The verifier step is the only step receiving `LOOPPLANE_STAGE_B_GITHUB_TOKEN`; the separate package/freeze/smoke step receives only the descriptor and MUST omit `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN` from wrappers, `npm` lifecycle commands, `uv`, PyInstaller, electron-builder, and every descendant. The run MUST NOT substitute the event's merge-branch `GITHUB_SHA`/`GITHUB_REF`, current PR head, actor identity, ADR/evidence, or repository files for reviewed commit/approver/prior locators. A manual rerun uses the original immutable event payload plus the same explicit prior-locator variables. Push/ordinary PR runs never substitute their actor/head/merge SHA as delivery authority.

The required Windows x64 delivery job runs on `windows-latest` or an approved GUI-capable Windows 11 runner and separates tokenized delivery verification from token-free sidecar/package wrappers, `electron-builder`, and the exact external-CWD `-Scenario all` artifact smoke. A Linux-only job, a bare `pyinstaller` command, or a source-mode smoke cannot satisfy SC-009.

Both `push` and `pull_request` path filters must include at least `.github/workflows/desktop.yml`, root `package.json`/`package-lock.json`, `pyproject.toml`/`uv.lock`, `apps/desktop/**`, `apps/web/**`, `packages/cowork-presentation/**`, `src/**`, `tests/**`, `scripts/verify-desktop-stage-b.ps1`, `scripts/build-desktop-sidecar.ps1`, `scripts/build-desktop-package.ps1`, `scripts/smoke-desktop-artifact.ps1`, `docs/adr/0015-desktop-cowork-boundary.md`, and `specs/078-desktop-cowork-parity/**`. Therefore every source, shared presentation, root-lock, Python authority/runtime, Host/runtime, verifier, package/smoke script, accepted digest, or contract input capable of changing the packaged artifact or its evidence triggers the Windows job.

Required focused suites cover:

- protocol framing/handshake/exhaustive method-capability mapping/shared recovery enum/version/correlation/idempotency/state/bounds/ordering/errors plus exactly 100 deterministic/property-generated malformed/stale/duplicate/cross-session cases, with a recorded `100/100` count, zero model-call sentinel, and zero secondary-surface disclosure findings;
- sidecar Host-only integration, approval/question/cancel, crash/EOF/shutdown teardown;
- sender validation, bounded schemas, global typing, and operation-specific IPC/preload/client ownership for every named app/session/Project/interaction/inspection/audit/agent-control/capability/workspace/backup/restore method, exhaustive recovery mapping, no raw escape hatch, and unsubscribe/renderer reload;
- canonical-root OS ownership-lock acquisition/alias/contention/crash-release/unsupported semantics with public-safe `busy`, zero Host, and no second interaction lease; profile principal isolation, Desktop Project membership/deletion, Host-owned star state, workspace revalidation/non-disclosure/relink, and unsent-draft exclusion;
- proof-before-Host bootstrap with explicit checkpoint/artifact `absent_uninitialized`, no sidecar store creation, first-normal-Host initialization, unexpected-payload fail-lock, exact pointer/proof/canonical publication-receipt authority, mutable-generation restart, POSIX physical-power-loss evidence, Windows process-crash evidence/limitation, unsupported pre-pointer rejection, and zero Host on ambiguity;
- multi-pane single-active behavior under the outer cross-process lock plus in-process-only draft/focus preservation;
- Host-owned capability/agent-control/cost projections and unavailable states;
- audit ordering/exclusions;
- Host portable snapshot export/read-only validation, artifact provenance/no-follow/identity consistency;
- backup allowlist/disclosure/integrity/unsafe archives; all-writer backup and restore lease windows raced against every session/interaction/Project/workspace/capability/profile/backup/restore mutation, explicitly including persisted `workspace.revalidate`, with bounded no-new-work teardown; exhaustive internal-cause-to-wire/recovery/`messageKey` mapping including the exact unknown fallback `-32603 internal_failure`/`true`/`restart_runtime`/`desktop.error.internal_failure`; reserved restore validation; platform-scoped candidate publication and canonical receipt; dual-slot full-preimage COW journals; independent candidate proof; proof post-effect/pre-ack startup adjudication; mutable-generation turn/restart; single-slot recovery; both-slot fail-lock; candidate/previous Host handover; and `relink_required` pre-lookup rejection of identical-ID stale bindings with post-proof cleanup.

### Build-only sidecar tool gate

The proposed tool is **PyInstaller 6.21.0** (stable PyPI release researched on 2026-07-30; supports Python `>=3.8,<3.16`), built for 078 on Python 3.12 / `x86_64-pc-windows-msvc`. It is absent from runtime dependencies/extras. Stage A permits creation of only the following two build-lock artifacts; Section 1's third and only other writable path is `specs/078-desktop-cowork-parity/implementation-evidence.md`, limited to the external Stage-A approval reference and lock-materialization/review evidence:

- `apps/desktop/sidecar/pyinstaller-build.in`, containing only `pyinstaller==6.21.0`;
- `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`, containing the candidate complete transitive wheel resolution and hashes.

The following command is used for initial Stage-A materialization and any later explicitly reviewed regeneration. It must produce no unexplained diff; the resulting exact file and SHA-256 become accepted build inputs only at Stage B:

```powershell
uv pip compile apps/desktop/sidecar/pyinstaller-build.in `
  --output-file apps/desktop/sidecar/pyinstaller-build-windows-py312.txt `
  --python-version 3.12 `
  --python-platform x86_64-pc-windows-msvc `
  --generate-hashes `
  --only-binary :all:
```

The sole reproducible sidecar install/freeze entry point is `scripts/build-desktop-sidecar.ps1`; the Desktop `build:sidecar` package script, CI, and maintained documentation must call this wrapper rather than bare `pyinstaller`, `pip install pyinstaller`, `uv tool run`, or another PATH/global/floating route. Final Stage B binds `pyproject.toml`, `uv.lock`, and this exact Desktop packaged-runtime extras allowlist: `anthropic`, `gemini`, `mcp`, `net`, `oauth`, and `openai`. The Desktop artifact excludes the existing `web`, `postgres`, and `otel` extras because it starts no HTTP server, uses profile-local SQLite, and does not claim optional telemetry; changing the allowlist or either Python authority file returns to final Stage B. PyInstaller remains a build-only graph from the Stage-A lock.

`scripts/verify-desktop-stage-b.ps1` delivery mode runs as the sole tokenized process and requires the shared immutable repository/PR/expected-approver inputs plus explicit T002 bootstrap, T005 final, and T090 delivery review-ID/expected-commit pairs. It refetches and proves the complete three-review authority chain, reruns the T002-to-T005 full-tree allowlist diff, and materializes exact reviewed bytes—not current worktree bytes—for the PyInstaller lock, `pyproject.toml`, `uv.lock`, npm manifests/root lock, and the complete delivery source snapshot into new verifier-owned absolute-path directories below `apps/desktop/sidecar/.build/accepted-inputs/<guid>/`. It uses create-new semantics, restrictive current-user ACLs where supported, rejects reparse/link/pre-existing entries, writes and flushes each regular file, validates source files against reviewed-tree Git blob identities, hashes the resulting bytes, marks them read-only, and returns a bounded non-secret JSON descriptor containing all three authority identities plus absolute paths and digests. It separately compares current bound artifacts/source while never passing mutable worktree dependency or source bytes to `uv`, npm, PyInstaller, or electron-builder. The verifier exits before any of those tools run.

From the accepted `pyproject.toml`/`uv.lock` snapshot, the wrapper runs `uv export --locked --no-dev --no-emit-project` with exactly the six accepted extras to create a hashed production-runtime requirements snapshot in the same accepted-input directory. It verifies and records that derived snapshot, then passes both the accepted PyInstaller lock snapshot and derived runtime requirements snapshot to one strict `uv pip sync`. The hardened PyInstaller spec resolves implementation source only from the delivery descriptor's reviewed `src/loopplane` plus `apps/desktop/sidecar` snapshot, while the synchronized environment supplies the complete accepted runtime dependency graph; it does not rely on current checkout source, an editable install, ambient `PYTHONPATH`, sibling environment, or separately installed LoopPlane runtime.

The normative sequence is:

```powershell
$inputRoot = Join-Path `
  "apps/desktop/sidecar/.build/accepted-inputs" `
  ([guid]::NewGuid().ToString("N"))
$venvRoot = Join-Path `
  "apps/desktop/sidecar/.build/pyinstaller-venvs" `
  ([guid]::NewGuid().ToString("N"))
$descriptorPath = Join-Path $inputRoot "accepted-inputs.json"

& "scripts/verify-desktop-stage-b.ps1" `
  -Mode Delivery `
  -RepositoryOwner $repositoryOwner `
  -RepositoryName $repositoryName `
  -PullRequestNumber $pullRequestNumber `
  -ExpectedApproverLogin $expectedApproverLogin `
  -BootstrapReviewId $bootstrapReviewId `
  -BootstrapExpectedCommitSha $bootstrapReviewedCommitSha `
  -FinalReviewId $finalReviewId `
  -FinalExpectedCommitSha $finalReviewedCommitSha `
  -DeliveryReviewId $deliveryReviewId `
  -DeliveryExpectedCommitSha $deliveryReviewedCommitSha `
  -MaterializeAcceptedInputs $inputRoot `
  -DescriptorPath $descriptorPath

Remove-Item Env:LOOPPLANE_STAGE_B_GITHUB_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
$accepted = Get-Content -LiteralPath $descriptorPath -Raw | ConvertFrom-Json

uv export `
  --project $accepted.pythonProjectRoot `
  --locked --no-dev --no-emit-project `
  --extra anthropic --extra gemini --extra mcp `
  --extra net --extra oauth --extra openai `
  --format requirements-txt `
  --output-file $accepted.runtimeRequirementsPath
& "scripts/verify-desktop-stage-b.ps1" `
  -AssertMaterializedInputs $descriptorPath

uv venv $venvRoot --python 3.12
$venvPython = Join-Path $venvRoot "Scripts/python.exe"
$venvPyInstaller = Join-Path $venvRoot "Scripts/pyinstaller.exe"
uv pip sync `
  $accepted.pyinstallerLockPath `
  $accepted.runtimeRequirementsPath `
  --python $venvPython `
  --require-hashes --only-binary :all: --strict
uv pip check --python $venvPython
& "scripts/verify-desktop-stage-b.ps1" `
  -AssertMaterializedInputs $descriptorPath
& $venvPyInstaller --version
& $venvPyInstaller `
  apps/desktop/sidecar/loopplane-sidecar.spec `
  --distpath apps/desktop/sidecar/dist `
  --workpath apps/desktop/sidecar/build `
  --noconfirm
```

Focused tests replace and restore the original worktree lock after the first verification and prove both `uv export` and `uv pip sync` still consume only descriptor-named accepted snapshot bytes with the recorded digests. Child-environment sentinels prove `npm`, npm lifecycle scripts, `uv`, PyInstaller, electron-builder, the sidecar wrapper, and every descendant receive no `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`; both wrappers fail before external execution when any such variable is present. Tests also prove a PyInstaller-only environment cannot pass, the exact six-extra production runtime graph is present, `loopplane` is collected from the descriptor's explicit delivery-reviewed `src/` snapshot, and no ambient/PATH/global tool is invoked. The accepted-input and venv roots are fresh GUID paths and disposable. The guarantee contains accidental/worktree drift and untrusted repository-file replacement; it does not claim resistance to a malicious process already executing as the same OS principal and able to rewrite the wrapper's private build directory or process memory. Such a principal is outside the local build threat model, and the contract does not describe repeated worktree hashing as closing that stronger attack.

Stage A may resolve and write hashes but may not install or invoke PyInstaller. Source-only dependency/regression gates may run after final Stage B/T005, but the first sidecar freeze/package/smoke occurs only after the distinct T090 Stage-C delivery review through the sole wrappers. A T005 dependency/design acceptance drift or T002-to-T005 full-tree allowlist violation returns to T005; a stale/substituted prior locator, delivery-review identity/state/expected-actor/PR-author/commit/tree/bundle/source-snapshot mismatch, or post-review implementation determinant change returns to T090 for a new delivery review. Tokenized three-review verification/materialization and token-free build/freeze/smoke are separate process/CI steps. Any missing/duplicate applicable locator or acceptance record, missing/insufficient explicit credential or permission, HTTP/rate/timeout/redirect/API-shape/truncated-tree failure, token/header/raw-body leakage, invalid submitted review, reused review ID, PyInstaller/root-lock/Python-authority drift, accepted-input materialization mismatch, runtime-extras change, credential-bearing child environment, environment-check failure, or direct/transitive diff stops T082/T086/T088/T090/T095 before another freeze, package, or smoke. The isolated accepted inputs, reviewed source snapshot, venv, work, and dist directories are untracked build outputs.

### Stage-B-bound root npm install snapshot

The final Stage-B record includes `Accepted Root package-lock SHA-256:` and the Stage-C delivery record proves those dependency bytes are unchanged while binding the implemented artifact determinants. `scripts/build-desktop-package.ps1` is the sole required clean package-build route. It:

1. accepts only a fresh descriptor path emitted by the immediately preceding isolated delivery-verifier process/step, offline-reasserts its materialized paths/digests, rejects any authority/GitHub token variable in its own environment, and never invokes network authority verification itself;
2. creates a fresh GUID build root only from the descriptor's reviewed source paths while excluding `.git`, `.superpowers`, `node_modules`, app-local lockfiles, local profiles/backups, accepted-input roots, and prior build outputs;
3. installs the exact T005-reviewed root `package.json`, root `package-lock.json`, and Web/Desktop/shared package manifests from the accepted descriptor into that build root using create-new/no-link checks, then verifies their accepted digests and confirms both app-local locks are absent;
4. runs `npm ci`, all lifecycle/shared/Web/Desktop build commands, and every descendant with an explicitly scrubbed environment that omits `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN`; and
5. invokes the sole sidecar wrapper with the same descriptor and delivery-reviewed source root under that token-free environment, copies only its completed frozen output into the snapshot's configured `extraResources`, runs `electron-builder` token-free there, and emits the unsigned artifact to the declared release-output path.

The required Windows CI artifact is therefore built from one isolated source snapshot whose implementation bytes equal the distinct delivery-reviewed commit and whose dependency manifests/lock equal the T005-reviewed bytes. Replacing/restoring checkout source or the root lock after verifier return cannot change the build or `npm ci` input. Focused tests spy the actual child-process working directory and descriptor paths, replace checkout source/lock between verification and build, and prove all consumers used only the read-only delivery/accepted snapshots. Local convenience installs outside this wrapper are non-authoritative and cannot satisfy SC-009. The same-OS-principal limitation stated for the sidecar build directory also applies; no stronger hostile-local-principal guarantee is claimed.

### Isolated built-artifact smoke

The normative Windows command performs the copy/install isolation itself:

```powershell
$checkoutRoot = (Resolve-Path ".").Path
$sourceArtifactRoot = (Resolve-Path "apps/desktop/release/win-unpacked").Path
$smokeScript = (Resolve-Path "scripts/smoke-desktop-artifact.ps1").Path
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("loopplane-078-smoke-" + [guid]::NewGuid().ToString("N"))
$artifactRoot = Join-Path $runRoot "artifact"
$scratchRoot = Join-Path $runRoot "scratch"
$evidencePath = Join-Path $runRoot "evidence.json"
New-Item -ItemType Directory -Path $runRoot | Out-Null
Copy-Item -Path $sourceArtifactRoot -Destination $artifactRoot -Recurse
$appExecutable = (Resolve-Path (Join-Path $artifactRoot "LoopPlane.exe")).Path
Push-Location $runRoot
try {
  powershell -NoProfile -ExecutionPolicy Bypass -File $smokeScript `
    -AppExecutable $appExecutable `
    -ScratchRoot $scratchRoot `
    -EvidencePath $evidencePath `
    -Scenario all
} finally {
  Pop-Location
}
```

The caller resolves the smoke script to an absolute checkout path before changing location, then invokes it only while the inherited working directory is the external `$runRoot`; the script path itself is not an application/state/evidence path. The script accepts exactly `happy`, `missing-sidecar`, `corrupt-sidecar`, `incompatible-sidecar`, or `all`. It canonicalizes every path and rejects an app executable, scratch/evidence path, generated profile, or inherited working directory inside `$checkoutRoot`. Each scenario receives fresh state below the external run root, `PYTHONPATH`/`NODE_PATH` are cleared, any modified **copied** resource is restored, and only bounded non-secret JSON evidence is written. `apps/desktop/electron/__tests__/packaging.test.ts` and `tests/integration/test_desktop_packaged_smoke.py` cover successful external-CWD invocation plus every checkout-path rejection, including direct invocation from a checkout CWD.

### Windows packaged interaction driver

The smoke script uses Windows' built-in .NET `UIAutomationClient` and `UIAutomationTypes` assemblies. No Playwright, Appium, WinAppDriver, CDP, DevTools, remote-debugging port, DOM injection, raw IPC/RPC, process facade, or local listener is allowed. Electron main accepts `--loopplane-packaged-smoke=<scenario>` only when `app.isPackaged`; it selects the already validated external scenario profile and starts the sidecar with a bounded credential-free deterministic configuration backed by the existing `loopplane.model.scripted.ScriptedModel`. This mode cannot select arbitrary RPC methods, tools, providers, paths, principals, request IDs, or mutation IDs and is unavailable to renderer JavaScript. On Windows only in this packaged-smoke mode, Electron main calls `app.setAccessibilitySupportEnabled(true)` after `app.whenReady()` and before creating the BrowserWindow; normal launches do not force accessibility support.

Electron/Chromium's actual packaged UIA provider is authoritative; 078 does not assume that HTML `id`, `data-testid`, `aria-*`, or a DOM attribute maps to UIA `AutomationIdProperty`. The same ordinary visible controls receive fixed non-localized smoke accessible names and explicit semantic roles/elements only in packaged-smoke mode; no hidden automation node or alternate renderer bridge is added. The driver locates exactly one element for each required `AutomationElement.NameProperty`/`AutomationElement.ControlTypeProperty` pair:

| NameProperty | ControlTypeProperty |
|---|---|
| `LoopPlane smoke runtime status` | `ControlType.Group` |
| `LoopPlane smoke new session` | `ControlType.Button` |
| `LoopPlane smoke prompt` | `ControlType.Edit` |
| `LoopPlane smoke submit` | `ControlType.Button` |
| `LoopPlane smoke latest outcome` | `ControlType.Group` |
| `LoopPlane smoke session list` | `ControlType.List` |
| `LoopPlane smoke runtime diagnostic` | `ControlType.Group` |

The driver starts the copied packaged executable with the bounded scenario flag, waits for its top-level window, and first proves all seven Name/ControlType pairs exist exactly once in the actual packaged accessibility tree. Absence, duplication, unexpected control type, or reliance on AutomationId/localized visible text fails the smoke before interaction. It then uses ordinary Value/Invoke/Window patterns; status, outcome, diagnostic, and persisted-session text are read only from descendants of their named visible Group/List container. In `happy` it creates a session, submits exact prompt `loopplane packaged smoke`, waits for exact terminal marker `loopplane-packaged-smoke-ok`, closes through the normal Window pattern, verifies child exit, relaunches the same scenario profile, and observes the prior session under `LoopPlane smoke session list`. Failure scenarios mutate only the copied sidecar resource before launch and wait for public-safe text under `LoopPlane smoke runtime diagnostic`. Automation timeouts and element lookups are bounded; evidence records only scenario, hashed artifact identity, the seven observed name/control-type pairs, bounded state/result enum, elapsed milliseconds, and orphan/listener booleans.

Smoke executes with:

- the copied/installed packaged artifact only;
- no separately installed LoopPlane runtime;
- no Web/local HTTP service or Desktop communication listener;
- the packaged-only bounded smoke mode and existing credential-free `ScriptedModel`;
- interaction solely through stable accessible controls and normal window lifecycle.

It proves:

1. the actual packaged accessibility tree exposes exactly one instance of all seven fixed Name/ControlType pairs, with accessibility forcing limited to packaged-smoke mode and no AutomationId/localized-text fallback;
2. packaged renderer/main/preload and sidecar initialize compatibly and status text below `LoopPlane smoke runtime status` becomes usable;
3. normal UI controls create/submit/observe one local session through exact `loopplane-packaged-smoke-ok`;
4. normal window shutdown leaves no orphan sidecar;
5. UI Automation observes the durable session after relaunch under `LoopPlane smoke session list`;
6. missing/corrupt/incompatible sidecar produces visible public-safe text below `LoopPlane smoke runtime diagnostic` within 10 seconds and does not mutate profile;
7. no source/dependency is resolved from the development checkout and no hidden automation transport is opened.

At least Windows is exercised by an actual GUI/artifact smoke for 078. Evidence for other platforms is claimed only when that platform runs successfully.

## 7. Public-safety evidence

Automated scans and adversarial fixtures prove authorized conversation/history and eligible referenced-artifact markers are routed only to those content surfaces. Outside those payloads, renderer-visible IPC status/events wrapper metadata/errors/audit/docs/test snapshots/manifest metadata/logs contain zero:

- credential/provider token/private key/password values;
- private rule expressions or capability configuration;
- absolute/canonical workspace or archive paths;
- rejected sensitive input echo;
- PID/process command line;
- raw exception/traceback/stderr/provider errors.

Fixtures use synthetic values. No real credentials or private local paths are committed. Trusted RPC path fields are tested by marker values and asserted absent from every outward projection/log/error/backup.

## 8. Rollback/default-preservation evidence

- Every wave is kept as a reviewable change boundary and can be reverted without depending on later waves.
- Existing Host resume with omitted scope retains current behavior.
- Desktop explicit SQLite selection does not change StorageConfig defaults.
- Protocol/profile/backup major mismatch fails closed; no silent downgrade/fallback.
- The canonical-root OS Profile Ownership Lock is acquired before recovery/store/Host work; contention/unsupported locking constructs zero Host, normal release follows bounded teardown, and process crash relies only on kernel release before later full recovery.
- Fresh bootstrap publishes/reopens the initial generation and canonical publication receipt with checkpoint/artifact `absent_uninitialized`, proves both payloads absent without creating/opening stores, then writes/rereads its receipt-bound proof before the exact pointer; only a pristine proof-without-pointer state may complete the embedded pointer, and first normal Host durable use retains store initialization ownership.
- Backup holds the all-writer Profile Mutation Lease before snapshot/profile serialization through archive finalization; `restore.validate` creates staging/token state only while reserving the same gate through commit/cancel/expiry/shutdown cleanup. Both reject every competing writer before dispatch and leave active authority unchanged until the restore pointer transition.
- POSIX publication uses regular-file/directory/both-parent `fsync` and same-filesystem rename under the exercised physical-power-loss claim. Windows uses supported-local-volume regular-file `FlushFileBuffers`, write-through move/replace, and reopen/current validation under process/application-crash consistency; sudden physical-power-loss persistence of both parent-directory entries is not claimed. Unsupported/error outcomes fail before pointer mutation.
- Commit writes/rereads both full-preimage journal slots with the canonical candidate receipt before pointer publication; COW transitions preserve one valid slot. The receipt proves publication lineage, not equality with later mutable active contents. A candidate remains active only under matching proof authority after runtime-owner installation.
- A definitive pre-proof failure restores the exact previous proof/pointer plus usable previous Host. If proof effect may have occurred but acknowledgement is uncertain, perform zero rollback/cleanup/binding/recovery mutation, stop dispatch, retain both slots, and let startup decide. One invalid slot is tolerated; no proof and no unambiguous slot fails locked. `relink_required` blocks binding lookup—including identical-ID stale bindings—until explicit relink, with stale cleanup only after proof authority.
- A packaging/build failure leaves the current source Desktop shell usable in development until the complete artifact pipeline is accepted; no half-built package is reported as delivered.
- If shared presentation clean-install proof fails, Web remains on its existing adapter/composition and the extraction is not considered complete.

## 9. Dependency and vulnerability boundary

- No new runtime dependency/direct optional extra is allowed under 078 without a separate gate.
- PyInstaller is exact-version build-only after approval.
- Existing `npm audit` findings are recorded as pre-existing risk evidence; 078 does not silently update lockfiles or dependencies outside the approved build graph.
- Any lockfile change must be attributable to the accepted workspace/build strategy and reviewed for transitive/runtime impact.

## 10. Completion and board transition

078 may transition to **Verified** only when:

- all FR-001 through FR-048 and SC-001 through SC-012 have task and evidence traceability;
- focused/full Python, Web, Desktop, browser, architecture, public-safety, backup, and packaging gates pass freshly;
- isolated Windows artifact smoke passes through the required fully triggered Windows x64 job and sole verifier-gated wrapper;
- the immutable T002/T005/T090 locator tuples independently refetch three live reviews on the same PR; each expected actor satisfies the C2 self-approval rule (default distinct from the PR author; equality permitted only when `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`), all three IDs remain pairwise distinct, the exact T002-to-T005 full-tree allowlist and final/delivery source/commit/tree/bundle/PyInstaller-lock/root-lock authorities still pass without trusting ADR/evidence, tokenized verification remains separated from token-free wrapper/build descendants, and acceptance records remain exact;
- docs and `[Unreleased]` changelog are synchronized;
- no excluded/unrelated/untracked files are included;
- actual failures/skips/platform gaps are reported honestly;
- maintainer approval exists for any ADR status transition and for board completion.

079 remains blocked until this transition. Version bump/release is a separate future human gate.
