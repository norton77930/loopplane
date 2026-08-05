# ADR 0015: Desktop cowork process, profile, and presentation boundary

- **Status**: Proposed (2026-07-30) — no gate is authorized; external-human Stage A may later write only `apps/desktop/sidecar/pyinstaller-build.in`, `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`, and `specs/078-desktop-cowork-parity/implementation-evidence.md`; T002 bootstrap authority is limited to T003/T004, no T006+ product implementation begins before distinct final external-human Stage-B acceptance, and no freeze/package/artifact smoke begins before the distinct post-implementation Stage-C delivery review.
- **Deciders**: LoopPlane maintainer; spec 078 (`desktop-cowork-parity`).
- **Supersedes / superseded by**: Does not supersede an existing ADR. It upgrades the unit-019
  Electron demo shell while preserving the runtime architecture established by prior ADRs.
- **Related**: Constitution **I** (ADR before load-bearing code), **III** (normalized events), **V**
  (Gateway-only tool execution), **VII** (public-safe diagnostics), **IX** (durability ownership), and
  **X** (default-preserving, testable, reversible). Contracts under
  `specs/078-desktop-cowork-parity/contracts/` are normative details of this decision.

## Context

LoopPlane already has a small Electron demo whose renderer can send arbitrary newline-delimited JSON
through preload and Electron main to a Python sidecar. The sidecar supports only a one-shot run path;
it does not version its protocol, correlate concurrent requests, own resumed interactive sessions,
handle approval/question/cancel reliably, preserve a durable Desktop profile, or prove packaged
operation outside a source checkout. The renderer-facing raw line tunnel also violates the intended
least-privilege Desktop boundary.

The existing runtime already owns session reconstruction, checkpoints, normalized runtime events,
Gateway enforcement, capability/agent-control projections, artifacts, and Web contracts. Desktop must
consume those seams rather than create a second runtime, policy engine, event vocabulary, or local Web
server. The unit additionally needs a stable local principal, private workspace bindings, multi-pane
read access with one interactive run, metadata-safe audit, portable recovery, shared Web presentation,
and deterministic packaging.

## Decision

- **D1 — Electron main is the sole process and protocol owner.** Desktop opens no local HTTP listener.
  Electron main alone spawns, initializes, reads, writes, drains, and terminates the bundled Python
  sidecar. Child error/exit/EOF, pending requests, stderr containment, graceful shutdown, and forced
  termination fallback are main-owned.

- **D2 — Use a bounded versioned private stdio protocol.** Main and sidecar communicate with JSON-RPC
  2.0 envelopes over strict UTF-8 LF-delimited stdio under product protocol
  `loopplane.desktop.stdio` version 1. Initialization negotiates exact methods, notifications,
  runtime-event schema, capabilities, and limits. Major/event-schema mismatch, malformed/oversized
  frames, unknown operations, invalid state, stale/cross-session identifiers, and queue overflow fail
  closed with public-safe errors. Main-generated IDs and process-lifetime duplicate-response caching
  prevent an acknowledged mutation from running twice; mutations are not retried after sidecar crash.

- **D3 — Preserve normalized RuntimeEvent payloads.** A `runtime.event` notification embeds exactly
  `json.loads(serialize_event(event))`. Desktop wrapper correlation is outside the event payload.
  Desktop control notifications do not become Event Bus events. `SCHEMA_VERSION`, event meanings,
  ordering, and EventSink ownership remain unchanged.

- **D4 — Preload exposes only named typed operations.** Production BrowserWindows keep context
  isolation and sandboxing enabled and Node integration disabled. The bundled HTML carries a restrictive
  local-asset CSP with no remote script/connect/object/base/form/frame capability. Electron main denies every
  unexpected top-frame navigation and every V1 `window.open` request, installs deny-by-default permission
  request/check handlers, and preserves only the exact packaged local renderer/preload path. Preload exposes a
  frozen, operation-specific facade; it never exposes `ipcRenderer`, channel strings, raw `send/on/invoke`,
  RPC methods/envelopes/IDs, process controls, or filesystem primitives. Electron main validates `senderFrame`
  and bounded payload schemas for every privileged call and wraps subscription callbacks without exposing
  Electron event objects.

- **D5 — Sidecar integrates runtime and portable storage only through `LoopPlaneHost`.** The sidecar does
  not import controller, checkpoint, model, tool, Gateway, live SQLite, or ArtifactStore internals for
  runtime/portable-storage operations. New interactions use existing `LoopPlaneHost.session()` and
  existing `Session` methods; session list/history/fork/rename/star/unstar/delete use existing public
  Host facades. Resumed interaction uses one additive Host async context manager that composes principal
  activation, controller resume, reviewer attachment, existing RunSink binding/replay, and the existing
  `Session` handle. Two default-unavailable `LoopPlaneHost` instance facades, backed only by an explicitly
  injected Desktop provider, export a consistent SQLite plus provenance-eligible artifact snapshot and
  validate an inactive staged snapshot. Because constructing `LoopPlaneHost` immediately performs normal
  assembly, startup instead calls the public non-instance `loopplane.host.validate_active_generation`
  facade. It proves pristine `absent_uninitialized` state or initialized current schema/SQLite ownership/
  artifact consistency through a Host-owned read-only provider with zero Host/normal-store construction,
  filesystem creation/mutation, or returned live storage handle/path. Existing Host/store owners create
  pristine stores only on first durable use.

- **D6 — Resume scope is additive and default-preserving.** `RuntimeController.resume()` receives an
  optional keyword-only `working_scope`. `None` preserves the current `Path.cwd()` behavior exactly.
  Existing `LoopPlaneHost.resume(session_id)` remains unchanged. Desktop supplies a scope only after
  current private workspace validation; no raw path is added to checkpoints, events, or Web
  projections.

- **D7 — One OS-owned process, opaque identity, and interactive lease per Desktop profile.** Before any
  recovery read or Host construction, the sidecar canonicalizes the profile root and acquires a
  generation-external OS-backed exclusive lock held for its process lifetime. A second process receives
  public-safe `busy` with zero Host; stale lock-file contents are never authority, and kernel crash release
  permits one later owner. The owning sidecar generates one immutable local `profile_id` and principal at
  profile creation; renderer input cannot choose or impersonate them. The profile may store portable
  Desktop Projects with opaque IDs, bounded labels, optional opaque Workspace References, and one-project-
  at-most session membership; deleting a project changes grouping only. Inside the sole owning process,
  one transient profile-wide interaction lease rejects a second acquisition before Host/model invocation.
  Multiple panes may read history/inspection/audit. Pane drafts are renderer-transient and excluded from
  restart persistence and backup. Existing Host active ownership remains a second guard.

- **D8 — Workspace references are portable; path bindings are device-private.** Native folder selection
  is Electron-main-owned. Main privately sends the chosen path to the sidecar, which canonicalizes and
  validates it and stores a profile-scoped opaque-reference-to-path binding outside the renderer,
  checkpoint records, events, Web projections, and backups. Renderer sees only safe ID, label,
  availability, and actions. Resume revalidates each use; restore marks every reference
  `relink_required` and never infers a path.

- **D9 — Desktop explicitly opts into existing SQLite checkpoint durability.** The sidecar constructs
  the Host with `StorageConfig` rooted in the active profile generation and
  `checkpoint_backend="sqlite"`. Existing checkpoint/artifact ownership and global/default storage
  behavior remain unchanged. Private capability configuration is not treated as portable profile
  data.

- **D10 — Turn audit is a bounded checkpoint-derived Host read projection.** An additive read-only Host
  facade derives stable logical-turn status/outcome metadata from existing checkpoint records. It does
  not write records, copy runtime events, or expose conversation/tool/artifact content, answers,
  principal, paths, private configuration, or raw errors. V1 does not claim per-event or complete
  approval/tool/model-subturn fidelity that current records cannot support.

- **D11 — Reuse presentation through a transport-neutral host.** Shared Web presentation depends on a
  narrow `CoworkPresentationHost`-style interface for session, interaction, inspection, settings, and
  capability semantics. Web adapts its existing `ApiClient + SessionTransport`; Desktop adapts the
  typed preload facade. Desktop does not pretend to be HTTP, and Web does not import Electron. Existing
  `/v1`, SSE/WS, generated contracts, auth, and reducer event meanings remain unchanged.

- **D12 — Portable backup is allowlisted, lossless, unencrypted, and generation-published.** V1 ZIP
  archives use a canonical versioned manifest, SHA-256 integrity, exact entry/size/ratio/path limits,
  regular files only, a Host-owned consistent SQLite snapshot, and only checkpoint-referenced existing
  Gateway ArtifactStore outputs whose provenance, metadata, root containment, no-follow identity, and
  before/after size are verified. They preserve full authorized user/model/tool session content,
  eligible referenced artifact bytes, Projects, safe preferences, and the profile principal, but exclude
  LoopPlane-owned credentials/tokens, private capability configuration, device-private workspace
  bindings, direct/recursive arbitrary workspace collection, unsent drafts, logs/errors, caches, PIDs,
  leases, and transient process state. The UI must explicitly disclose that authorized content/artifacts
  may retain credentials, paths, or workspace excerpts and that integrity is not encryption/authenticity.

- **D13 — Restore validation reserves mutation ownership; publication uses platform-scoped durability,
  redundant recovery preimages, and an independent active proof.** Restore never uses `extractall()` or
  merges in place. Backup holds the Profile Mutation Lease from before Host snapshot/profile serialization
  through archive finalization. `restore.validate` atomically reserves it through commit/cancel/expiry/
  shutdown. While either owns/reserves the lease, every competing session/interaction/Project/workspace/
  capability/backup/restore writer fails `busy` before Host/profile dispatch; only owning restore continuation
  and bounded teardown may pass. Validation checks archive/profile/checkpoint/artifact consistency through
  Host-owned seams.
  Generation publication deliberately has two guarantees: supported POSIX local filesystems use regular-
  file and directory `fsync`, same-filesystem rename, and both parent-directory `fsync`s for the exercised
  physical-power-loss claim; the required Windows artifact accepts supported local filesystems, uses
  regular-file `FlushFileBuffers`, same-volume `MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` or equivalent,
  and post-move reopen/current consistency validation for process/application-crash consistency. It does
  **not** claim undocumented directory-handle flush semantics or sudden physical-power-loss persistence of
  both parent-directory entries; Stage B must accept this limitation. Publication emits a canonical
  immutable Generation Publication Receipt bound into pointer/proof/journals. The active generation becomes
  mutable after Host open, so startup validates receipt lineage plus current profile/SQLite/artifact state,
  not publication-time file hashes. A fresh zero-session generation instead declares checkpoint/artifact
  state `absent_uninitialized`; pre-Host validation calls a public non-instance
  `loopplane.host.validate_active_generation(source, expectation, *, provider=None)` facade that proves
  pristine absence or validates initialized current schema/SQLite ownership/artifact consistency without
  constructing `LoopPlaneHost` or normal stores, creating/mutating filesystem entries, or returning storage
  handles/paths. A Host-owned injectable read-only provider supports deterministic fault tests, and existing
  Host/store owners create pristine stores on first durable use. Fresh bootstrap is proof-before-pointer/Host.

  Restore commit writes/rereads two checksummed COW slots containing exact previous proof/pointer preimages,
  candidate pointer/receipt, and recovery lineage. A transition preserves one complete valid slot. After
  candidate Host readiness and runtime-owner swap, a matching Active Generation Proof authorizes candidate
  startup. A definitive pre-proof failure rolls back exactly. If proof replace/flush may have taken effect
  but acknowledgement/reread is uncertain, the process performs no rollback, cleanup, binding deletion, or
  further recovery-record mutation; it stops dispatch, retains both journals, and startup alone adjudicates
  matching proof versus journal rollback. Restored `relink_required` state is checked before any binding
  lookup, so identical-ID pre-restore bindings cannot revive; cleanup waits until proof authority. No proof
  and no unambiguous journal authority fails locked with zero Host rather than guessing a retained generation.

- **D14 — Packaging binds complete Python/npm dependency authorities and consumes accepted snapshots.**
  PyInstaller **6.21.0** is build-only. Stage A may create only `pyinstaller-build.in`, the Windows-x64/
  Python-3.12 hashed wheel lock, and bounded evidence; it accepts neither this ADR nor install/build/product
  work. T002's submitted bootstrap review binds the design, `pyproject.toml`, `uv.lock`, and candidate
  PyInstaller lock and authorizes only T003 RED tests plus T004 verifier/dependency-graph materialization.
  T004 creates every complete final root/Web/Desktop/shared manifest field—including dependencies, workspaces,
  scripts, entrypoints, exports, files, and other package metadata—before the sole root lock and removes both
  app-local locks, without install/build. T005 requires immutable T002/T005 locator tuples and a distinct submitted final review over that post-T004
  commit. It independently refetches both complete trees and accepts only the exact T003 verifier-test/T004
  verifier/four-manifest/root-lock/bounded-bootstrap-evidence additions or modifications plus the two app-lock
  deletions; any other path/type/Git-mode/blob difference fails closed. After acceptance those manifests and
  the root lock remain immutable, and any needed metadata/lock change returns to T004 plus a new T005 before
  install/build. T005 then content-binds the verifier/tests, both Python authorities, the exact packaged extras
  `anthropic`, `gemini`, `mcp`, `net`, `oauth`, `openai`, the PyInstaller lock, all npm manifests, root lock,
  and app-lock absence. Only T005 accepts this ADR and records identical PyInstaller/root-lock digests in
  ADR/evidence.

  Final-mode `scripts/verify-desktop-stage-b.ps1` refetches T002/T005, enforces their complete-tree allowlist,
  fetches exact accepted Python/npm bytes into fresh absolute-path, no-link, current-user build-input snapshots,
  and returns a digest descriptor. Delivery mode later receives T002/T005/T090 immutable locators, refetches
  all three authorities, and emits one bounded non-secret descriptor containing prior and delivery identities;
  current worktree files are compared but never passed to package managers. The tokenized verifier process then
  exits. Token-free `scripts/build-desktop-sidecar.ps1` derives a hashed runtime requirements snapshot from
  accepted `pyproject.toml`/`uv.lock`, strict-syncs it together with the accepted PyInstaller lock into a fresh
  venv, validates the complete runtime graph, and freezes only the descriptor-named Stage-C-reviewed
  `src/loopplane` plus sidecar source. Token-free `scripts/build-desktop-package.ps1` copies that reviewed source
  into a fresh build root, installs only final-reviewed root/app/shared manifest/lock bytes there, verifies
  app-lock absence, runs `npm ci`/all lifecycle/frontend builds only there, delegates freeze only to the sidecar
  wrapper against the same reviewed source snapshot, and runs `electron-builder`. Both wrappers reject any
  authority/GitHub token variable and scrub every external descendant environment. Tests replace/restore
  checkout locks after verification and prove package managers consume only descriptor snapshots. Bare/global/PATH PyInstaller, direct install,
  ambient Python/Node paths, a PyInstaller-only environment, and checkout-root install as final artifact
  evidence are prohibited. The guarantee covers repository/worktree replacement and accidental drift, not a
  malicious process already running as the same OS principal with access to private build memory/directories.

  The normative Windows smoke copies the whole `win-unpacked` tree to a fresh external `%TEMP%` root and uses
  the contract-defined Windows UI Automation driver through ordinary visible controls—never raw IPC/RPC,
  DevTools, remote debugging, or a local listener—to create/submit/observe/restart one deterministic
  credential-free session and validate 10-second missing/corrupt/incompatible-sidecar diagnostics. In
  packaged-smoke mode only, Electron enables accessibility after readiness and before BrowserWindow creation;
  the actual packaged UIA tree must expose exactly one of each frozen Name/ControlType Group/Button/Edit/List
  pair. DOM-to-AutomationId assumptions and localized-text fallback are not authority. Path-filtered Windows source gates cover root/Python authorities, Desktop/Web/shared/source/tests, all four
  delivery scripts, ADR, and 078 artifacts. A separate `pull_request_review`-submitted Windows x64 delivery job
  takes T090 locators from the event, T002/T005 locators from maintainer-controlled repository variables, and the
  expected approver from its repository variable. An isolated tokenized step refetches all three authorities,
  proves same PR/pairwise-distinct IDs/the T002-to-T005 full-tree allowlist, and emits the descriptor. A separate
  token-free step invokes the package wrapper plus exact smoke only on the reviewed source and proves no build
  descendant inherited GitHub token variables. Linux/apps-only green is not artifact evidence. Signing, release, and untested-platform claims remain excluded.

- **D15 — Contracts and the serial human gates are binding.** The four technical contracts plus delivery
  contract define exact V1 limits, methods, projections, inclusion/exclusion, verification, and rollback.
  External-human Stage A may authorize writes only to the two exact PyInstaller lock paths and bounded
  `implementation-evidence.md`; it leaves this ADR Proposed and grants no install/build/source/commit/push/PR
  authority. Stage B then requires two distinct submitted GitHub PR reviews, and Stage C requires a third
  post-implementation delivery review before freeze/package/smoke. Each review author must be a non-bot
  repository owner/member/collaborator with API-visible `APPROVED`, API-controlled review ID/node ID, non-null
  `submitted_at`, `user.type=User`, allowed `author_association`, login equal to an immutable expected-approver
  input, login satisfying the C2 self-approval rule (default different case-insensitively from the singular PR author's login; equality only when `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` is exactly `true`), and `commit_id` equal to the
  exact review commit. Comments, inline or pending reviews, unauthorized PR-author self-approval when the C2 switch is off, and review-body text are
  non-authoritative. The verifier receives immutable shared owner/repository/PR/expected-approver inputs plus
  T002 for bootstrap, T002+T005 for final, or T002+T005+T090 review-ID/expected-commit pairs for delivery; prior
  locators never come from ADR/evidence/config, mutable refs, or list/search APIs. It reads a short-lived
  credential only from `LOOPPLANE_STAGE_B_GITHUB_TOKEN` in the isolated verifier process; no `GH_TOKEN`/
  `GITHUB_TOKEN`, `gh auth`, git-credential, evidence-text, or persisted-login fallback is allowed. It uses
  minimum `contents: read`/`pull-requests: read` permissions plus version-pinned singular PR/review/commit/tree/
  blob REST resources, requires every complete non-truncated tree, disables redirects, and bounds deadlines.
  Final and delivery modes refetch prior authorities and enforce the exact T002-to-T005 full-tree allowlist.
  Missing/insufficient credentials, stale/substituted locators, HTTP/rate/timeout/API-shape failure, unauthorized
  or unexpected actor, unauthorized self-approval, full-tree-diff/commit/artifact mismatch, or truncated authority data emits
  no descriptor or acceptance write. Tokens, authorization headers, and raw response bodies never enter logs,
  evidence, artifacts, or snapshots. After descriptor emission the verifier exits; wrappers and every build
  descendant reject or scrub all GitHub token variables. `pull_request_target` is not used to bypass fork trust.

  T002's bootstrap review binds the design, `pyproject.toml`, `uv.lock`, and candidate PyInstaller lock and
  authorizes only T003 RED delivery tests plus T004 three-mode verifier and dependency-manifest/root-lock
  materialization; ADR status remains Proposed. T005 requires immutable T002/T005 locator tuples and a different
  final review ID over the post-T004 commit. It refetches both complete trees and rejects every path/type/mode/
  blob difference outside the exact T003/T004 manifest/root-lock/bootstrap-evidence/app-lock-deletion allowlist,
  then binds only the pre-implementation design, verifier/tests, exact packaged Python extras, all npm manifests,
  sole root lock, and both app-local-lock absence records. Only successful T005 verification may accept this ADR,
  write the final acceptance blocks, and unlock T006+. T090 then requires immutable T002/T005/T090 locators and
  a third distinct review over the post-T089 implementation commit; it refetches all three authorities, proves
  same PR/pairwise-distinct IDs, reruns the full-tree allowlist, content-binds actual product/wrapper/workflow/
  smoke source, and materializes the exact reviewed source snapshot before the first freeze/package/smoke. It
  does not change this ADR's status. Every applicable verifier run refetches review identity/state/actor/
  `commit_id` and derives tree, canonical bundle, source, and lock digests from reviewed commits without trusting
  records. Missing/dismissed approval, stale/substituted locator, expected-actor/unauthorized-self-approval or commit mismatch,
  review-ID reuse, full-tree-diff/authority/source/artifact drift, credential-bearing build environment, or
  app-lock reappearance requires a new applicable submitted review or corrected token-free invocation.
  Automated/system/agent/teammate/self-authored repository records never approve a gate. Discovery of a
  required new dependency/default, Event/checkpoint/Gateway change, or Web outward-contract change stops
  implementation and requires a separate decision.

## Consequences

- Desktop becomes a local-first first-class surface without opening a port or duplicating runtime
  enforcement.
- Renderer compromise is constrained to named validated operations; it cannot write arbitrary sidecar
  messages, choose principal/path, or directly invoke tools/process/filesystem APIs.
- Existing Host/controller/event/checkpoint/Gateway/Web behavior remains unchanged when Desktop is not
  launched; the only runtime additions are public additive Host resume/audit/portable-snapshot seams,
  the non-instance active-generation read-only validator, default-preserving parameters, and a default-`None`
  snapshot provider.
- A profile can survive restart and portable restore with Projects/session membership intact, but
  restored workspaces always require explicit relinking, unsent drafts are intentionally absent, and
  private capability/provider configuration must be re-established.
- Full recovery and perfect automatic secret removal are intentionally not both claimed. Authorized
  conversation and eligible Gateway-artifact content is lossless and may retain sensitive values or
  workspace excerpts, while secondary metadata remains public-safe; backups therefore require an
  explicit unencrypted-sensitive-content warning and user-protected destination.
- Host-owned SQLite/provenance-checked artifact snapshots, restore reservations, redundant full-preimage
  journals, and an independent active proof add implementation/test complexity, but avoid sidecar
  reach-through, a second session database, and unrecoverable ambiguity after pointer publication.
- Multi-pane remains presentation/read concurrency, not parallel interactive execution.
- V1 audit is honest but narrower than a forensic event ledger. A richer durable audit would require a
  separate checkpoint/event decision.
- Build reproducibility becomes part of feature completion; source-only test success cannot mark 078
  Verified.

## Alternatives rejected

- **Run a local Web API/WebSocket service**: rejected because it opens an unnecessary listener and
  couples local lifecycle/security to the Web surface.
- **Keep or extend the raw NDJSON `op` tunnel**: rejected because it lacks bounded versioning,
  correlation, state, idempotency, and renderer least privilege.
- **Expose a generic preload `invoke(method, params)`**: rejected because it recreates the raw escape
  hatch under a typed-looking name.
- **Let sidecar call controller/checkpoint/tool internals**: rejected because it bypasses the public Host
  facade and architecture ownership.
- **One Host per pane or renderer-only locking**: rejected because it permits races/bypass and conflicts
  with the single-active runtime invariant.
- **Persist raw workspace paths in sessions/checkpoints/renderer storage**: rejected because it leaks
  local topology and makes portable recovery unsafe.
- **Copy the Web app or make Desktop imitate HTTP**: rejected because behavior/contracts would drift and
  Desktop-specific native/profile semantics do not fit the Web transport.
- **Archive raw events as audit**: rejected because it creates a second event store and leaks payloads.
- **Metadata-only backup or heuristic secret/path redaction**: rejected because the maintainer selected
  full honest history; heuristics can both miss secrets and corrupt recovery.
- **Application-level encrypted backup in 078**: deferred because it requires cryptographic dependency,
  password/key storage, rotation, and recovery decisions.
- **In-place restore/extract-all**: rejected because partial or malicious input can corrupt the active
  profile.
- **Read live SQLite/ArtifactStore paths from the sidecar**: rejected because it violates the Host-only
  boundary and cannot guarantee a consistent provenance-checked snapshot.
- **Treat `restore.validate` as read-only or publish without durable recovery evidence**: rejected because
  staging/token reservation is a durable mutation and a crash after pointer replacement otherwise cannot
  distinguish verified completion from incomplete publication.
- **Rewrite one restore-journal file in place or use its deletion as the only commit proof**: rejected
  because one torn/truncated/missing transition can destroy the sole exact previous pointer/proof preimage.
  Two copy-on-write full-preimage slots remain until a separate matching active proof is durable.
- **Claim Windows parent-directory physical-power-loss durability from directory-handle flush**: rejected
  because reviewed Microsoft contracts do not document that unprivileged guarantee. 078 instead requires
  documented regular-file flush/write-through move/reopen on supported local filesystems, fail-closed
  startup validation, and an explicit Stage-B-accepted process-crash-only guarantee; unsupported volumes
  fail before pointer publication.
- **Add PyInstaller as a runtime dependency, leave it unpinned, or pin only the direct package**:
  rejected because packaging tooling is build-only and the complete transitive build resolution must
  be hash-constrained for reproducibility.
- **Require full ADR acceptance of an exact lock before authorizing its creation**: rejected as circular;
  narrow Stage A materializes review artifacts only, while Stage B remains the sole implementation gate.

## Acceptance record required

An external-human Stage A record may authorize only the exact lock-materialization command and these three paths: `apps/desktop/sidecar/pyinstaller-build.in`, `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`, and `specs/078-desktop-cowork-parity/implementation-evidence.md`. It leaves this ADR **Proposed** and grants no installation/build/product authority. System notifications, automated agents/audits, teammate messages, assistant statements, and self-authored evidence are not approval.

Stage A grants no commit/push/PR authority. Separate explicit authorization must place candidate artifacts on an exact review commit. T002 then requires a submitted bootstrap review whose immutable commit binds the complete Proposed design bundle, `pyproject.toml`, `uv.lock`, direct PyInstaller input, and candidate transitive lock. T002 verifies the review API identity, live state, actor, exact `commit_id`, commit/tree, canonical bundle, lock digest, and complete path/type/Git-mode/blob inventory digest, then records only bounded bootstrap evidence in `implementation-evidence.md`. Later modes receive the T002 review ID/expected commit as immutable inputs and rederive those values rather than trusting this record. It keeps this ADR Proposed and authorizes only T003/T004.

T005 requires a distinct submitted final review over the exact post-T004 commit. That pre-implementation commit itself contains and therefore binds:

1. Desktop RPC V1, IPC/presentation, profile/workspace/audit, backup/restore, and delivery contracts;
2. the approved design for additive Host resume/audit/portable-snapshot seams, default-`None` snapshot provider, public non-instance active-generation validator, and resume default preservation—not future implementation bytes;
3. the approved design for the OS-backed Profile Ownership Lock, all-writer Profile Mutation Lease, Project/star ownership, transient drafts, proof-before-Host bootstrap, immutable receipt versus mutable active state, fixed backup/restore error map, platform-honest durability, reserved validation, dual-slot exact recovery, proof-effect/ack startup adjudication, stale-binding pre-lookup denial, and fail-lock rules—not future implementation bytes;
4. T003 RED delivery tests and T004 bootstrap/final/delivery verifier implementation;
5. accepted `pyproject.toml`/`uv.lock`, exact packaged extras `anthropic`, `gemini`, `mcp`, `net`, `oauth`, and `openai`, plus the exact build-only PyInstaller 6.21.0 Windows/Python-3.12 complete transitive hash lock;
6. complete final root/Web/Desktop/shared package manifests—including dependencies/workspaces/scripts/entrypoints/exports/files metadata—sole root `package-lock.json`, explicit absence of both app-local lockfiles, and the rule that later manifest/lock mutation requires a new T005 before install/build;
7. the specified accepted-input, sole sidecar/package wrapper, Windows CI, and UI-Automation external-CWD artifact-smoke contracts—not the T006–T089 implementation that does not yet exist;
8. acknowledgement that V1 backup is unencrypted and losslessly retains authorized user-, model-, and tool-produced conversation/eligible-artifact content that may contain sensitive values or workspace excerpts; and
9. acknowledgement that implementation cannot expand into excluded runtime/Web/release changes.

T005 final mode must receive immutable T002/T005 locator tuples, refetch the singular PR plus both reviews/commits/complete trees/blobs through the explicit credential/API seam, independently rederive the bootstrap authority, and verify API URL, numeric ID, node ID, exact non-null `submitted_at`, live `APPROVED`, `user.type=User`, OWNER/MEMBER/COLLABORATOR association, exact expected approver under the C2 self-approval rule (default distinct from the PR author), exact `commit_id`, complete non-truncated trees, and non-reuse of the bootstrap review ID. It must enforce the exact T002-to-T005 full-tree allowlist over path/type/Git-mode/blob/add/modify/delete before deriving the canonical final bundle, PyInstaller-lock digest, and root-lock digest, and compare current bound artifacts while normalizing only this ADR's Status value and bounded acceptance blocks. Any missing/insufficient credential or permission, HTTP/rate/timeout/redirect/API-shape failure, expected-actor/unauthorized-self-approval mismatch, or token/header/raw-body leakage fails closed before ADR/evidence mutation. Only then may T005 change this header to `Accepted` and populate exactly one identical final field set here and in `implementation-evidence.md`: `Stage B Approval API URL:`, `Stage B Approval ID:`, `Stage B Approval Node ID:`, `Stage B Approval Submitted At:`, `Stage B Approver Login:`, `Stage B Reviewed Commit SHA:`, `Stage B Reviewed Tree SHA:`, `Stage B Review Bundle SHA-256:`, `Accepted PyInstaller lock SHA-256:`, and `Accepted Root package-lock SHA-256:`. Any review, actor, commit, bundle, Python/npm authority, lock, or absence-record drift requires a new final submitted review. The evidence file cannot authorize itself.

T090 separately requires immutable T002/T005/T090 locator tuples and a third submitted Stage-C delivery review over the exact post-T089 implementation commit, with a review ID distinct from T002/T005 and the same expected-approver identity checks under the C2 self-approval rule. Delivery mode independently refetches all three review/commit/complete-tree/blob authorities, proves same PR and pairwise-distinct IDs, reruns the T002-to-T005 full-tree allowlist, and rederives the prior bundles/locks without trusting ADR/evidence. It binds the actual product, verifier/wrapper, workflow, PyInstaller-spec, packaging/accessibility, and UI-Automation smoke source, revalidates the T005 manifests/locks/Python authorities, and materializes exact reviewed source before the first freeze/package/smoke. It emits a bounded non-secret descriptor and exits; all wrappers/build descendants then run with GitHub token variables absent. It does not change this ADR or its acceptance block; its distinct machine-readable delivery field set belongs only in `implementation-evidence.md`. Any stale/substituted locator, full-tree-diff, delivery-review, implementation determinant, or credential-bearing child-environment drift requires a new applicable review or corrected token-free invocation.

<!-- STAGE-B-ACCEPTANCE START -->
<!-- T005 populates this bounded block only after final external Stage-B verification succeeds. -->
<!-- STAGE-B-ACCEPTANCE END -->
