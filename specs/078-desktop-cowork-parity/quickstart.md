# Quickstart Validation Guide: Desktop Cowork Parity

This guide defines the runnable validation sequence for 078 after the required human gate and implementation. It does not authorize source implementation and does not replace the normative contracts.

## 1. Current gate status

- ADR 0015 is **Proposed**; Stage A, both Stage-B reviews, and Stage C are all unauthorized.
- Stage A requires external-human authorization and may write only `apps/desktop/sidecar/pyinstaller-build.in`, `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`, and `specs/078-desktop-cowork-parity/implementation-evidence.md`. It does not authorize any other write, installation, or build.
- Stage B has two distinct submitted GitHub PR reviews. T002's bootstrap review binds the design, `pyproject.toml`, `uv.lock`, and candidate PyInstaller lock and authorizes only T003 RED delivery tests plus T004 bootstrap/final/delivery verifier and dependency-manifest/root-lock materialization while ADR 0015 remains Proposed. T005 requires immutable T002/T005 review-ID/commit locator pairs and a different final review over the exact post-T004 pre-implementation commit; it independently refetches both complete trees, rejects every T002-to-T005 path/type/Git-mode/blob difference outside the exact T003/T004 manifest/root-lock/bootstrap-evidence/app-lock-deletion allowlist, and then binds design/T003/T004, exact six-extra Python graph, all npm manifests, sole root lock, both app-lock absence records, and both lock digests. Only successful T005 verification may accept ADR 0015 and unlock T006+. Stage C at T090 requires immutable T002/T005/T090 review-ID/commit locator pairs and a third review over the exact post-T089 implementation commit; delivery mode independently refetches all three authorities, proves same PR/pairwise-distinct IDs/the T002-to-T005 full-tree allowlist, rederives prior bundles/locks without trusting ADR/evidence, and binds actual product/wrapper/workflow/PyInstaller-spec/packaging/accessibility/smoke source before any freeze/package/artifact smoke. It leaves ADR status unchanged. Every review must be a live submitted `APPROVED` review by a non-bot owner/member/collaborator whose login equals the immutable expected approver and satisfies the C2 self-approval rule (default differs case-insensitively from the singular PR author; equality only when `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`). Comments, unauthorized self-approval when the C2 switch is off, inline/pending reviews, editable review-body text, ambient authentication state, and system/agent/audit/teammate/self-authored records are non-authoritative. All checks require immutable shared owner/repository/PR/expected-approver inputs plus every mode-required review-ID/expected-commit pair and a non-empty short-lived `LOOPPLANE_STAGE_B_GITHUB_TOKEN` confined to the verifier process. Prior locators cannot come from ADR/evidence/config. After descriptor emission, all GitHub token variables are removed before package/freeze/smoke. Missing/insufficient credentials, stale/substituted locators, full-tree-diff violation, HTTP/rate/timeout/redirect/API-shape/truncated-tree failure, expected-actor/PR-author/commit/review-ID mismatch, authority/artifact/source drift, credential-bearing build descendants, credential leakage, or app-lock reappearance fails closed and requires a new applicable submitted review or corrected token-free invocation.
- No version bump, release, signing, deployment, commit, or push is part of this guide.

## 2. Normative references

- [Feature specification](spec.md)
- [Implementation plan](plan.md)
- [Data model](data-model.md)
- [Desktop stdio RPC V1](contracts/desktop-rpc-v1.md)
- [Desktop IPC and Shared Presentation Boundary](contracts/desktop-ipc-and-presentation.md)
- [Desktop Profile, Workspace, Resume, and Turn Audit](contracts/desktop-profile-workspace-and-audit.md)
- [Portable Desktop Backup and Restore V1](contracts/backup-and-restore.md)
- [Delivery, Verification, Rollback, and Human Gate](contracts/delivery-and-human-gate.md)
- [ADR 0015](../../docs/adr/0015-desktop-cowork-boundary.md)

## 3. Prerequisites after final Stage-B approval and before Stage-C delivery

- Windows 11 machine for the required actual Desktop GUI/artifact smoke.
- Repository checkout with no unrelated tracked changes included in the validation result.
- Python 3.12 and `uv` available.
- Node.js/npm version supported by the repository CI.
- Final-reviewed root npm workspace/lock is the sole app/workspace lock; `apps/web/package-lock.json` and `apps/desktop/package-lock.json` are absent.
- Final-reviewed `pyproject.toml`, `uv.lock`, `pyinstaller-build.in`, and `pyinstaller-build-windows-py312.txt` are bound with the exact packaged extras `anthropic`, `gemini`, `mcp`, `net`, `oauth`, and `openai`; `web`, `postgres`, and `otel` are excluded from the packaged graph.
- ADR 0015 and `implementation-evidence.md` each contain exactly one matching final Stage-B API URL/ID/node-ID/submitted-at/approver/reviewed-commit/reviewed-tree/review-bundle/PyInstaller-lock/root-lock field set. The referenced final review remains live and its ID differs from the bootstrap review; current authorities match the commit-derived inventory.
- Verifier invocations receive exact shared owner/repository/PR/expected-approver values plus T002 for bootstrap, T002+T005 for final, and T002+T005+T090 review-ID/expected-commit pairs for delivery; the verifier fetches the singular PR and rejects an expected reviewer equal to its author. Do not derive prior locators from ADR/evidence/config, set `GH_TOKEN`/`GITHUB_TOKEN` as fallback, or rely on `gh auth`/git credentials. CI grants only `contents: read` and `pull-requests: read`; obtains T002/T005 IDs and commit SHAs only from `LOOPPLANE_DESKTOP_BOOTSTRAP_REVIEW_ID`, `LOOPPLANE_DESKTOP_BOOTSTRAP_COMMIT_SHA`, `LOOPPLANE_DESKTOP_FINAL_REVIEW_ID`, and `LOOPPLANE_DESKTOP_FINAL_COMMIT_SHA`; obtains expected approver only from `LOOPPLANE_DESKTOP_EXPECTED_APPROVER`; uses path-filtered push/PR runs for source gates and `pull_request_review` `submitted` for delivery packaging; rejects event/API disagreement; and never uses `pull_request_target` to bypass fork permissions. `${{ github.token }}` is mapped only into the isolated verifier step. The separate package/freeze/smoke step receives only the non-secret descriptor and no `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`; API, permission, prior-locator, full-tree-diff, or child-environment failure produces no accepted build.
- Python 3.12 is used for the required Windows x64 sidecar build. Before running either package wrapper, obtain T090's distinct Stage-C delivery review, run the three-locator verifier in its isolated tokenized process, require its evidence-only delivery field set and bounded descriptor, then remove every GitHub token variable. PyInstaller/runtime/npm inputs are consumed only from T005-accepted snapshots and implementation source only from the T090-reviewed source snapshot by token-free `scripts/build-desktop-sidecar.ps1` and `scripts/build-desktop-package.ps1`. Bare/global/PATH PyInstaller, direct install, `uv tool run`, ambient paths, mutable checkout source/locks as package inputs, credential-bearing child environments, and copied install/freeze routes are prohibited.

Do not use real provider credentials in protocol/public-safety tests. The isolated smoke uses the repository's credential-free model/smoke adapter.

## 4. Clean install and static gates

From repository root after final Stage B, these are source-regression gates only; their checkout-root `npm ci` result is not package-artifact evidence. Section 14's accepted-snapshot package wrapper is the sole SC-009 artifact route:

```powershell
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy

npm ci
npm --workspace @loopplane/web run typecheck
npm --workspace @loopplane/desktop run typecheck
```

Expected:

- locked Python and JavaScript installs succeed without dependency lookup from sibling `node_modules`;
- root `package-lock.json` is the only app/workspace lock and app-local installs do not recreate divergent locks;
- no new runtime dependency/extra or new third-party JavaScript package name appears outside the approved migration;
- Python/TypeScript static checks pass;
- Desktop does not compile shared source via `../web/src` alias.

## 5. Focused Host and sidecar contract validation

Use the final task-defined focused paths; the following command shape is the required grouping:

```powershell
uv run pytest -q `
  tests/contract/test_desktop_rpc_v1.py `
  tests/contract/test_desktop_public_safety.py `
  tests/unit/test_host_turn_audit.py `
  tests/unit/test_host_portable_snapshot.py `
  tests/unit/test_desktop_profile.py `
  tests/unit/test_desktop_workspace.py `
  tests/unit/test_desktop_backup.py `
  tests/unit/test_desktop_restore.py `
  tests/integration/test_host_session.py `
  tests/integration/test_host_durability.py `
  tests/integration/test_desktop_sidecar.py `
  tests/integration/test_desktop_profile.py `
  tests/integration/test_desktop_backup.py `
  tests/integration/test_desktop_restore.py
```

Expected evidence:

- omitted resume scope preserves current `Path.cwd()` behavior;
- validated scope supports resumed submit/cancel/approval/question and is released on every exit;
- sidecar uses Host public facades and existing `serialize_event` output only;
- initialize/version/event-schema/method allowlist and all V1 bounds are enforced;
- stale, duplicate, unknown, wrong-method, and cross-session identifiers produce no unintended side effect;
- the canonical profile-root OS ownership lock is acquired before recovery/store/Host work; an aliased-root or second process receives public-safe `busy` with zero Host, process crash releases kernel ownership, and unsupported/remote/ambiguous locking fails closed;
- sidecar crash/EOF/writer failure releases pending waits, subscriptions, the inner interaction lease, reviewer/sink, and process-held profile ownership;
- fixed profile principal survives restart and cross-principal IDs are enumeration-safe;
- fresh-profile bootstrap publishes/reopens the initial generation and canonical publication receipt with checkpoint/artifact states `absent_uninitialized`, then calls the public non-instance `loopplane.host.validate_active_generation(...)` facade to prove both payloads absent without opening/creating either store; initialized startup uses the same facade's dedicated read-only schema/SQLite ownership/artifact-consistency path; both paths create zero Host/normal stores/files, write/reread the receipt-bound proof before the exact pointer, and construct no Host until pointer/proof/receipt lineage and current-state validation match; first normal Host durable use owns store initialization, while unexpected pre-Host data or every non-pristine mismatch fails locked with zero Host;
- POSIX publication covers regular-file/bottom-up-directory/both-parent `fsync` and same-filesystem rename under the exercised physical-power-loss claim; Windows covers supported-local-volume regular-file `FlushFileBuffers`, write-through move/replace, reopen/current validation, and process termination under the narrower process/application-crash claim, with no parent-directory sudden-power-loss claim; unsupported outcomes fail before pointer mutation;
- a normal committed turn mutates checkpoints/artifacts/profile state and restart still validates current state without comparing it to publication-time hashes;
- session star/unstar uses the existing Host state, while Desktop Projects safely persist grouping without deleting sessions/workspaces;
- Workspace References expose no path and a moved/missing/restored workspace requires relink; explicit `workspace.revalidate` persists availability/private validation timestamps only through the Profile Mutation Lease and fails `busy` before any write while backup/restore owns it;
- unsent drafts remain renderer-transient and are absent after restart/backup;
- audit is stable, checkpoint-derived, metadata-safe, and creates no record/event schema change;
- Host-owned snapshot export creates a consistent SQLite plus provenance-eligible referenced-artifact inventory; inactive staged validation remains an instance facade, while startup current-generation validation uses the public non-instance Host facade with zero normal store/Host construction, filesystem creation, or sidecar live-store reach-through;
- backup/restore hold one all-writer Profile Mutation Lease for their complete normative windows, and every competing session/interaction/Project/workspace/capability/profile/backup/restore mutation is rejected before Host/profile dispatch except owning commit/cancel and bounded teardown that starts no durable work;
- every backup/restore internal cause selects the exact contract-defined RPC code/category, retryability, required-or-absent shared recovery value, and fixed `messageKey`; the unknown fallback is exactly `-32603 internal_failure`/`true`/`restart_runtime`/`desktop.error.internal_failure`, and internal cause labels never become outward categories.

## 6. RPC adversarial matrix

Run the protocol suite against at least these classes:

1. malformed UTF-8, JSON, duplicate keys, excessive depth/keys;
2. top-level batch/scalar/client notification/pre-initialize request;
3. incompatible protocol name/major/minor and runtime-event schema;
4. control/event frame overflow, prompt/title limit, request/subscription/queue capacity;
5. duplicate request ID with same input, duplicate ID with changed method/params, stale/unknown response;
6. out-of-order/gapped/duplicated notification sequence and wrong subscription/session/run correlation;
7. invalid interaction transitions, second active acquisition, completed approval/question answer, cancel/shutdown races;
8. every backup/restore internal cause row, including both publication variants, exact rollback, and the exact unknown fallback `-32603 internal_failure`/`true`/`restart_runtime`/`desktop.error.internal_failure`, plus combined/missing-required/unexpected recovery and message-key mismatches;
9. child spawn error, stderr noise, stdout EOF, process exit, blocked graceful shutdown.

Expected: the suite executes exactly 100 deterministic/property-generated cases across these classes and records `100/100`; every case is contained, the model-call sentinel remains zero, no mutation replays after crash, the secondary-surface sensitive-marker scan remains zero, and renderer errors stay bounded/public-safe.

## 7. Electron main/preload/client gates

```powershell
npm --workspace @loopplane/desktop test -- --run
npm --workspace @loopplane/desktop run build
```

Expected evidence:

- production BrowserWindow settings retain context isolation/sandbox and disable Node integration;
- all privileged IPC validates trusted `senderFrame` and bounded payload schema;
- focused main/preload/global-typing tests own every named facade family: app status/shutdown/subscription; session list/history/rename/star/delete/fork/create/resume/release; Projects; interaction; inspection/audit/agent controls; capability list/action; workspaces/native pickers; and backup/restore;
- each named operation has an operation-specific handler/preload method, typed public-safe result/error, and exhaustive one-to-one `DesktopRecovery` mapping where recovery is present; unknown/combined recovery values fail as protocol errors;
- no `window.api.send`, `onLine`, generic `invoke`, raw channel/method, `ipcRenderer`, process, or filesystem escape hatch remains;
- native chooser cancellation mutates nothing and absolute selected paths never reach renderer payloads/errors/logs;
- subscriptions are shared where required, return idempotent unsubscribe, and clean up on pane/window/sidecar teardown;
- pending renderer requests reject visibly on sidecar incompatibility/crash/EOF rather than hanging;
- main/preload/renderer outputs are emitted at paths consumed by Electron packaging.

## 8. Shared Web/Desktop presentation regression

```powershell
npm --workspace @loopplane/cowork-presentation run typecheck
npm --workspace @loopplane/cowork-presentation test -- --run
npm --workspace @loopplane/web test -- --run
npm --workspace @loopplane/web run build
npm --workspace @loopplane/desktop test -- --run
```

Expected:

- Web continues through its existing HTTP/SSE/WS adapters and outward contracts;
- Desktop continues through typed preload and never imports/imitates `ApiClient`;
- both surfaces deliver equivalent chat reducer, approval/question, settings, inspection, cost/agent-control unavailable-state semantics;
- Desktop-only Project/workspace/pane/backup capabilities are absent from Web;
- Desktop session star state remains Host-owned and Project membership remains profile-owned;
- three panes can show history/inspection while exactly one interaction is accepted;
- second-run rejection preserves drafts, histories, focus, and inspection state;
- keyboard/focus, high zoom, forced colors, reduced motion, and bilingual behavior remain usable.

Run the concrete Chromium matrix used by T050/T094:

1. start the accepted-snapshot Web build/dev surface on `127.0.0.1:4173` without changing manifests/locks;
2. use the already available Playwright-MCP/Chromium runtime—no new project dependency—with deterministic frontend interception following `specs/081-web-capability-delivery-remediation/quickstart.md` §5;
3. exercise 1440×900, 1024×768, 768×1024, 375×812, 640×900, and 320×800 in en/zh-TW; light across all rows; dark/reduced-motion at 1440 and 375; forced colors at 375; keyboard-only pane/composer/sidebar/dialog flow, visible focus, focus return, and no document/body horizontal overflow;
4. save only ignored local evidence under `.playwright-mcp/spec078-desktop-cowork/results.json` plus bounded screenshots; record Chromium version, fixture identity, assertion/failure/console-error counts in `implementation-evidence.md`; never stage `.playwright-mcp/**`.

The pre-078 reference is 79/79; report the fresh literal result rather than inheriting that count.

## 9. Workspace/profile restart scenario

Use an isolated temporary Desktop profile and temporary workspace:

1. launch with an empty profile and capture bootstrap evidence that the initial generation receipt, `proof_kind="bootstrap"` proof, and exact active pointer are each durable/reread-valid before the first Host is constructed;
2. select the workspace through the native chooser;
3. create a Project associated with the Workspace Reference, create a session, assign/star it, and complete one turn;
4. close cleanly and assert no sidecar remains;
5. relaunch and inspect prior Project membership, star state, history, and audit while confirming unsent drafts did not persist;
6. resume and complete another turn using current validation;
7. remove/recreate the Project to prove grouping changes do not delete sessions or bindings, then move/remove/replace the workspace target and relaunch;
8. inspect history, attempt interaction, then explicitly relink to a newly selected folder.

Expected:

- bootstrap fault injection before proof leaves no committed profile; after proof/before pointer it completes only the embedded exact pointer for a pristine receipt-valid generation; every other pointer/proof/receipt mismatch or unsupported durability state fails locked before Host construction;
- pristine bootstrap sees absent SQLite/artifact payloads and does not create either before Host authority; unexpected payload presence fails locked;
- while the first process holds the canonical-root OS lock, a second process using the same or aliased root receives `busy`, creates zero Host/interaction lease, and mutates nothing; forced first-process termination releases ownership so a later process reruns recovery successfully;
- one principal remains stable across steps 1–8;
- renderer sees only Workspace Reference ID/label/availability/actions;
- unavailable or `relink_required` scope blocks interaction before binding lookup and never silently uses a stale path, including an old device-private binding with identical restored profile/workspace IDs;
- relink failure/cancel preserves previous binding and history;
- no workspace contents are deleted or copied into profile storage.

## 10. Multi-pane and lifecycle scenario

1. open three persisted sessions in three panes;
2. start an interaction in pane A;
3. inspect history/audit/settings in panes B and C;
4. submit from pane B;
5. switch focus using keyboard and open/close the right sidebar;
6. trigger and answer approval/question in pane A;
7. cancel or complete the run;
8. close/reorder panes and start a new interaction in pane B.

Expected:

- step 4 is rejected before a second model call;
- safe projection identifies the interaction owner without principal/path/PID;
- pane drafts/history/focus are preserved;
- approval/question applies only to the exact pending request;
- lease is released after terminal/cancel/teardown, permitting step 8.

## 11. Backup round trip

With an idle temporary profile containing Projects, starred sessions, safe preferences, referenced artifacts, opaque workspaces, an unsent draft, and synthetic user-, model-, and tool-produced sensitive marker content:

1. request `backup.describe` and record the unencrypted/full-history disclosure;
2. decline acknowledgement and assert no destination chooser/archive mutation;
3. acknowledge, select an explicit destination, and create backup;
4. inspect archive and canonical manifest in a test harness;
5. restore into an isolated profile through validate preview + explicit commit;
6. without restarting the sidecar, inspect sessions/history/artifacts/audit and complete one non-workspace write to prove the live runtime owner uses only the candidate-generation Host;
7. restart, confirm the same candidate data, then attempt workspace-dependent work before and after explicit relink.

Expected:

- synthetic authorized user/model/tool conversation and eligible-artifact markers remain lossless, demonstrating honest disclosure, while unsent drafts are absent;
- LoopPlane-owned synthetic credentials/private config, Workspace Bindings/paths, direct/recursive workspace files, logs/errors/PIDs/leases are absent;
- manifest entries, sizes, hashes, totals, format/profile/disclosure versions are valid and contain no sensitive content metadata;
- profile/principal/Projects/session membership/star/history/provenance-eligible referenced artifacts restore consistently;
- every restored Workspace Reference is `relink_required` before native relink.

## 12. Restore adversarial and rollback matrix

Exercise:

- malformed ZIP/manifest/JSON/duplicate keys;
- unsupported major/minor/profile schema/compression;
- undeclared/missing/duplicate/case-fold/Unicode-normalization entries;
- traversal, absolute, drive, UNC, backslash, alternate-stream, long/control-character names;
- symlink/special entry and central/local metadata mismatch;
- size/count/ratio/actual streamed byte overflow and hash mismatch;
- corrupt SQLite/schema/integrity/principal ownership and missing referenced artifact;
- backup acquisition before snapshot/profile serialization and restore reservation before staging, each raced against session create/rename/star/fork/delete, interactive open/submit/answer, Project/workspace/capability/profile mutation, competing backup/restore, owning restore commit/cancel, and bounded shutdown/cancel/release teardown; all competing durable work is rejected before Host/profile dispatch and teardown starts none;
- fresh-bootstrap interruption across POSIX regular-file/directory/both-parent `fsync` and rename boundaries, and Windows supported-volume/regular-file `FlushFileBuffers`/write-through move/reopen/process-termination boundaries; then final publication receipt, bootstrap-proof, pointer, unsupported API/volume, and every pristine versus non-pristine proof-without-pointer case;
- restore interruption/failure before staging, during streaming, after reservation/staging, throughout the applicable POSIX or Windows candidate publication matrix, current schema/SQLite/artifact validation, canonical publication-receipt creation, and unsupported-durability decision; assert the active pointer is untouched throughout pre-pointer boundaries;
- interruption during each pointer/proof/journal temp write, regular-file flush, platform write-through replace/post-replace validation, after both `prepared` slots, after pointer replace, after COW `published`, during candidate Host readiness/old-Host close/runtime-owner swap, before proof publication, **after proof write/flush may have taken effect but before successful reread/acknowledgement**, after `verified`, and between one-at-a-time cleanup;
- independently tear, truncate, corrupt, and remove journal slot A or B at every post-pointer boundary; inject conflicting/equal-sequence lineages; remove/corrupt both slots before proof; and remove remaining journals after a valid matching candidate proof;
- source archive replacement between validate and commit;
- insufficient destination/staging space;
- each internal failure cause mapped to its exact wire code/category, retryability, required-or-absent recovery, and fixed localization key, including both `publication_failed` variants, `rolled_back`, and unknown-cause containment.

Expected:

- unsafe details are not echoed;
- no in-place extraction or active-profile merge occurs;
- POSIX satisfies its file/directory/both-parent `fsync` publication contract and exercised physical-power-loss evidence; Windows satisfies supported-local-volume regular-file flush/write-through move/reopen/process-crash evidence while explicitly making no both-parent sudden-power-loss claim. Unsupported/error outcomes expose only `durability_unsupported` or `publication_failed` and mutate no pointer;
- every pre-pointer restore failure leaves the active authority byte-identical under the platform guarantee; bootstrap never constructs a Host without matching pointer/proof/publication-receipt lineage and current generation validation;
- before pointer publication, both checksummed `prepared` slots reread validly with identical full previous proof/pointer preimages and the canonical candidate receipt/digest; every state transition preserves another complete valid slot until candidate proof authority;
- any one torn/truncated/corrupt/missing slot restores the exact saved prior proof/pointer pair before Host construction, while conflict or both slots unavailable before proof fail locked with no Host;
- a definitive pre-proof in-process failure restores a usable previous-generation Host; if proof effect is possible but acknowledgement is uncertain, the process performs zero rollback/cleanup/binding mutation, retains both journals, stops dispatch, and startup alone decides matching proof versus exact rollback;
- after proof authority, later journal state cannot force rollback and post-commit I/O uses only the candidate Host; after a normal turn mutates state, restart validates current schema/SQLite/artifacts without publication-time hash equality;
- cleanup interruption remains recoverable from a surviving slot or matching proof;
- `relink_required` is checked before binding lookup, so pointer switch/rollback cannot revive an identical-ID stale Workspace Binding; stale cleanup waits until proof authority;
- orphan staging/inactive generation is never activated silently and stale reservations are released deterministically;
- the all-writer lease covers backup through finalization and restore through terminal reservation cleanup with no competing writer leakage or teardown-started durable work;
- internal cause names are absent from outward categories, and the exact code/category/retryability/recovery/`messageKey` table is exhaustive.

## 13. Full regression gates

```powershell
uv run pytest -q
uv build

npm --workspace @loopplane/web run typecheck
npm --workspace @loopplane/web test -- --run
npm --workspace @loopplane/web run build
npm --workspace @loopplane/desktop run typecheck
npm --workspace @loopplane/desktop test -- --run
npm --workspace @loopplane/desktop run build
```

Reference baselines:

- Python: `1496 passed, 8 skipped, 1 warning`;
- Web: 57 files / 192 Vitest;
- Desktop: 3 files / 12 Vitest;
- Chromium: 79/79.

Report fresh counts, skips, warnings, failures, and isolated reruns honestly. Do not run the full Python suite concurrently with multi-agent workflows.

## 14. Build sidecar and Desktop artifact

After narrow Stage A authorization, the candidate lock is initially materialized with this command. Any later regeneration is also an explicit review action; an unexplained diff blocks Stage B or packaging:

```powershell
uv pip compile apps/desktop/sidecar/pyinstaller-build.in `
  --output-file apps/desktop/sidecar/pyinstaller-build-windows-py312.txt `
  --python-version 3.12 `
  --python-platform x86_64-pc-windows-msvc `
  --generate-hashes `
  --only-binary :all:
```

After all source gates pass, obtain the third T090 delivery review over the exact implementation commit and rerun delivery mode on that same commit. Only then is the sole sidecar route `scripts/build-desktop-sidecar.ps1` and the sole complete artifact route `scripts/build-desktop-package.ps1`. Do not run bare/global `pyinstaller`, direct install, `uv tool run`, checkout-root `npm ci` as final artifact evidence, or copied variants. The sidecar wrapper follows this contract-defined shape with fresh GUID roots and descriptor-named accepted inputs:

```powershell
$inputRoot = Join-Path "apps/desktop/sidecar/.build/accepted-inputs" ([guid]::NewGuid().ToString("N"))
$venvRoot = Join-Path "apps/desktop/sidecar/.build/pyinstaller-venvs" ([guid]::NewGuid().ToString("N"))
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

& "scripts/verify-desktop-stage-b.ps1" -AssertMaterializedInputs $descriptorPath
uv venv $venvRoot --python 3.12
$venvPython = Join-Path $venvRoot "Scripts/python.exe"
$venvPyInstaller = Join-Path $venvRoot "Scripts/pyinstaller.exe"
uv pip sync `
  $accepted.pyinstallerLockPath `
  $accepted.runtimeRequirementsPath `
  --python $venvPython `
  --require-hashes --only-binary :all: --strict
uv pip check --python $venvPython
& "scripts/verify-desktop-stage-b.ps1" -AssertMaterializedInputs $descriptorPath
& $venvPyInstaller --version
& $venvPyInstaller apps/desktop/sidecar/loopplane-sidecar.spec `
  --distpath apps/desktop/sidecar/dist `
  --workpath apps/desktop/sidecar/build `
  --noconfirm
```

The verifier uses the pinned GitHub API version and singular PR/review/commit/tree/blob resources for all three explicit locator tuples, requires `user.type=User`, OWNER/MEMBER/COLLABORATOR association, exact expected approver, C2 self-approval rule (default PR-author inequality; exact `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL=true` permits equality), exact `commit_id`, same PR, pairwise-distinct IDs, complete trees, and the exact T002-to-T005 full-tree allowlist. It disables redirects, enforces 15 seconds per request and 60 seconds total, and permits at most one transport-or-502/503/504 retry with no auth/not-found/rate retry. Missing credentials, stale/substituted locators, 401/403/404/429/rate exhaustion, timeout, malformed/unexpected response, full-tree-diff violation, or authority mismatch emits no descriptor; token, authorization headers, and raw response bodies are never printed or written.

After the verifier exits, the production wrapper uses absolute paths, create-new/no-link checks, read-only accepted dependency bytes, a bounded digest descriptor, and only the exact delivery-reviewed `src/loopplane`/sidecar source snapshot. Package managers and build tools never consume mutable worktree dependency or source files and never inherit `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`; wrappers fail if those variables remain and explicitly scrub every external descendant environment. `scripts/build-desktop-package.ps1` independently materializes the T005-reviewed npm manifests/root lock and T090-reviewed implementation into a fresh GUID build root while excluding `.git`, `.superpowers`, `node_modules`, app-local locks, profiles/backups, and old outputs, verifies the two app locks remain absent, and runs `npm ci`, shared/Web/Desktop builds, the sidecar wrapper, and electron-builder only in that isolated snapshot:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-desktop-sidecar.ps1 -DescriptorPath $descriptorPath
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-desktop-package.ps1 -DescriptorPath $descriptorPath
```

Expected:

- the descriptor records independently refetched T002/T005/T090 review/commit/tree/bundle identities, same-PR/pairwise-distinct-ID and expected-approver/PR-author checks, the T002-to-T005 full-tree allowlist result, reviewed source identity, accepted PyInstaller/root-lock digests, derived runtime-requirements digest, and exactly PyInstaller 6.21.0;
- the frozen graph contains LoopPlane plus exactly the six accepted runtime extras and excludes `web`, `postgres`, and `otel`;
- checkout-lock replace/restore fault tests cannot alter either Python or npm install input;
- Electron package contains emitted main/preload/renderer assets and bundled sidecar at configured paths;
- package entrypoints resolve no `.ts` source or checkout-relative resource;
- signing/notarization is not claimed.

Build outputs remain untracked unless a separate delivery rule explicitly says otherwise. The stated isolation covers repository/worktree drift, not a malicious process already running as the same OS principal with access to private build memory/directories.

The required CI evidence combines path-filtered Windows source gates covering the workflow, root npm/Python authorities, all Desktop/Web/shared/source/test determinants, all four delivery scripts, ADR 0015, and every 078 artifact with a separate `pull_request_review`-submitted Windows x64 delivery job. That job uses the event only for immutable T090 PR/review/commit locators, maintainer repository variables for the T002/T005 locators and expected approver, and an isolated tokenized verifier step that refetches all three authorities and emits a descriptor. It rejects disagreement and full-tree-diff violations. A separate token-free step invokes the package wrapper against the exact reviewed source, delegates freeze only to the sidecar wrapper, proves all build descendants lack GitHub token variables, and runs the external-CWD `-Scenario all` command. Linux/apps-only checks are supplemental and cannot satisfy SC-009.

## 15. Isolated built-artifact smoke

Run this one normative command. It performs the required copy before resolving the executable, so the tested application tree is never the checkout build directory:

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

The command resolves the smoke script to an absolute checkout path before `Push-Location`, then invokes it only from the external `$runRoot`; the script path itself is not an application/state/evidence path. `-Scenario` accepts exactly `happy`, `missing-sidecar`, `corrupt-sidecar`, `incompatible-sidecar`, or `all`. The script canonicalizes all paths and rejects an app executable, scratch root, evidence path, generated profile, or inherited working directory that is inside `$checkoutRoot`. It creates fresh per-scenario state, clears `PYTHONPATH`/`NODE_PATH`, restores any temporarily altered **copied** packaged resource, and emits only bounded non-secret JSON evidence. Packaging contract tests must cover successful external-CWD invocation and every checkout-path rejection, including direct invocation from a checkout CWD.

The Windows interaction driver uses only built-in .NET `UIAutomationClient` and `UIAutomationTypes`; it adds no Playwright/Appium/WinAppDriver dependency. The packaged process accepts a bounded `--loopplane-packaged-smoke=<scenario>` launch mode only when `app.isPackaged`, with the external scratch profile selected by Electron main and a credential-free deterministic Host configuration using the existing `ScriptedModel`. On Windows only in this mode, Electron calls `app.setAccessibilitySupportEnabled(true)` after `app.whenReady()` and before BrowserWindow creation; normal launches do not force it. The same ordinary visible controls expose fixed non-localized names and semantic roles/elements. The PowerShell driver must find exactly one actual packaged UIA element for each pair: `LoopPlane smoke runtime status`/Group, `LoopPlane smoke new session`/Button, `LoopPlane smoke prompt`/Edit, `LoopPlane smoke submit`/Button, `LoopPlane smoke latest outcome`/Group, `LoopPlane smoke session list`/List, and `LoopPlane smoke runtime diagnostic`/Group. It submits the prompt `loopplane packaged smoke`, waits for exact terminal marker `loopplane-packaged-smoke-ok` below the named outcome group, closes through the normal window pattern, relaunches, and observes the prior session below the named list. Failure scenarios observe public-safe text below the named diagnostic group. No DOM-to-AutomationId assumption, localized-text fallback, CDP, DevTools/remote-debugging flag, raw IPC/RPC/process facade, local listener, DOM injection, or renderer-supplied path is permitted.

Validate:

1. no application source or sibling `node_modules` is accessible;
2. no local Desktop communication listener is opened;
3. the actual packaged accessibility tree exposes exactly one instance of all seven fixed Name/ControlType pairs, with no AutomationId/localized-text fallback;
4. handshake succeeds and status below `LoopPlane smoke runtime status` reports usable through Windows UI Automation;
5. `LoopPlane smoke prompt`/Edit and `LoopPlane smoke submit`/Button drive one credential-free session to exact `loopplane-packaged-smoke-ok` below `LoopPlane smoke latest outcome`;
6. normal window close leaves no sidecar;
7. relaunch exposes the prior session below `LoopPlane smoke session list`;
8. missing, corrupt, and protocol-incompatible sidecar variants expose public-safe text below `LoopPlane smoke runtime diagnostic` within 10 seconds and preserve their fresh profiles.

Only Windows is mandatory for 078's real GUI smoke. Do not report another platform as verified unless its artifact actually passes.

## 16. Architecture and public-safety review

Run existing architecture/conformance guards and targeted scans. Review the final diff for:

- the only tool invocation site remains Gateway;
- Event Bus/RunSink/checkpoint record schema/generated Web contracts/defaults are unchanged;
- sidecar imports only approved Host/public modules for runtime work;
- no raw IPC/RPC/path/principal/config escape hatch;
- authorized conversation/eligible-artifact sensitive markers are routed only to those content surfaces and never copied into status/audit/errors/logs/diagnostics/manifest metadata;
- no real credentials/private paths in fixtures/docs/logs/snapshots;
- `.superpowers/**`, local profiles/backups/logs/tokens/PIDs/build outputs/unrelated files excluded;
- exact build-tool pin and root-lock change limited to the approved strategy.

## 17. Completion evidence

Before proposing board transition:

- map FR-001–FR-048 and SC-001–SC-012 to tasks and passing evidence;
- record and API-refetch distinct bootstrap/final Stage-B plus post-implementation Stage-C delivery submitted reviews through immutable invocation inputs and the explicit short-lived token seam; verify three distinct IDs, expected-approver equality, C2 self-approval rule (default PR-author inequality), minimum permissions, all fail-closed credential/HTTP/rate/timeout/redirect/API-shape/truncated-tree cases, zero token/header/raw-body leakage, exact reviewed design/dependency and delivery commit/tree/bundle/source/PyInstaller-lock/root-lock fields, identical ADR/evidence Stage-B records, the evidence-only delivery record, and unchanged Python/npm authorities;
- record fresh Python/Web/Desktop/Chromium/package/public-safety results;
- synchronize required docs, including `docs/manual-qa.md`, and `[Unreleased]` without version bump/release;
- document OS profile-lock contention/alias/crash-release/zero-Host behavior, pristine absent-uninitialized bootstrap, all-writer backup/restore races, exhaustive internal-cause error mapping, Host snapshot/provenance, Project/star, draft exclusion, immutable publication receipt versus mutable active state, POSIX physical-power-loss versus Windows process-crash publication evidence and Windows limitation, proof-effect/ack startup adjudication, stale identical-ID binding rejection, restore reservation, dual-slot/single-slot-loss/fail-lock/exact rollback, sole-wrapper/PATH-sentinel/repeated-verifier evidence, full Windows CI triggers, and all untested platforms/findings;
- request maintainer completion approval.

Only then may `docs/loopplane-agent-board.md` mark 078 Verified and unblock 079.
