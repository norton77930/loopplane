# Research: Desktop Cowork Parity

## Decision 1: Replace the raw line tunnel with a versioned local RPC protocol

**Decision**: Use JSON-RPC 2.0 envelopes over UTF-8, LF-delimited stdio with a product protocol identifier `loopplane.desktop.stdio` and version `1.0`. Electron main is the only RPC client; the Python sidecar is the only RPC server. Batch requests, client notifications, arbitrary method names, and renderer-generated RPC identifiers are not supported.

The first request on every connection is `initialize`. It negotiates protocol major/minor, runtime-event schema version, exact method/notification allowlists, limits, and safe capability availability. A major-version or runtime-event-schema mismatch fails closed before the renderer becomes interactive.

**Rationale**: The current `{op:"run"}` NDJSON bridge has no version, correlation, session identity, state validation, or interactive control path. JSON-RPC supplies a familiar request/response/error envelope without a new dependency; the product protocol version remains independent from JSON-RPC's fixed `"2.0"` marker.

**Alternatives considered**:

- Extend the current `op` messages: rejected because correlation, versioning, errors, and method governance would remain ad hoc.
- Start a local HTTP/WebSocket server: rejected because 078 is local-first and opens no port.
- Add a third-party RPC library: rejected because the standard libraries and existing AnyIO runtime are sufficient and no new dependency is authorized.

## Decision 2: Bound framing, concurrency, and failure behavior explicitly

**Decision**: Define the following V1 defaults in the protocol contract, subject to the 078 human gate:

- initialization timeout: 5 seconds;
- graceful shutdown timeout: 5 seconds before forced termination;
- control request/response frame: 1 MiB maximum;
- normalized runtime-event notification frame: 8 MiB maximum;
- prompt: 64 KiB UTF-8 maximum;
- ordinary title/reason/label text: 4 KiB maximum;
- concurrent outstanding requests: 64 maximum;
- active subscriptions: 8 maximum;
- outbound notification queue: 128 items or 16 MiB, whichever is reached first;
- JSON depth: 32 and object keys: 128 maximum.

The receiver counts bytes before strict UTF-8 decode and JSON parse. Electron main uses a byte-oriented line scanner plus Node's built-in `StringDecoder` so split multibyte characters are not corrupted. The sidecar has one serialized stdout writer. Queue overflow, frame overflow, parse failure, child `error`/`exit`, or unexpected EOF transitions the connection to a public-safe failed state; no mutation is retried automatically after process failure.

**Rationale**: The current main process converts each chunk to a string before line splitting and has no frame, queue, handshake, or child-failure bounds. Bounded deterministic failure is safer than partial parsing or silent hangs.

**Alternatives considered**:

- Unlimited frames/queues: rejected as an avoidable memory and availability risk.
- Truncate oversized events: rejected because it would mutate normalized event meaning.
- Retry mutations after crash: rejected because the caller cannot know whether a model run or durable mutation already began.

## Decision 3: Electron main owns privileged IPC and sidecar lifecycle

**Decision**: Keep `contextIsolation: true`, `sandbox: true`, and `nodeIntegration: false`. Replace `window.api.send/onLine` with a frozen, typed `window.loopplaneDesktop` facade. Preload exposes named operations and wrapped subscriptions only; it never exposes `ipcRenderer`, an IPC channel string, RPC method strings, RPC identifiers, raw JSON, process handles, or filesystem APIs.

Electron main registers per-operation `ipcMain.handle` handlers, validates `event.senderFrame` against the one trusted local renderer URL/frame, validates every payload, and maps each operation to an allowlisted sidecar method. Main owns spawn, handshake, stdout decode, stderr containment, child error/exit/EOF handling, graceful shutdown, forced kill fallback, native file/directory pickers, and renderer subscription cleanup.

**Rationale**: Electron's official security guidance recommends context isolation/sandboxing, narrow `contextBridge` APIs rather than exposing `ipcRenderer`, and sender validation for privileged IPC. The current preload exposes an unrestricted line tunnel and the current main process forwards it directly to stdin.

**Alternatives considered**:

- Generic `invoke(method, params)`: rejected because it recreates a raw RPC escape hatch in the renderer.
- Pass Electron IPC event objects to renderer callbacks: rejected because they expose privileged Electron capabilities.
- Let the renderer spawn or write to the sidecar: rejected because process and protocol ownership would be untrusted and duplicated.

**Reference**: Electron security/context-isolation guidance at <https://github.com/electron/electron/blob/main/docs/tutorial/security.md> and <https://github.com/electron/electron/blob/main/docs/tutorial/context-isolation.md>.

## Decision 4: Preserve runtime events byte-for-byte inside transport wrappers

**Decision**: Every runtime-event notification contains `json.loads(serialize_event(event))` as its event payload. The wrapper may add only Desktop correlation metadata (`notification_seq`, `subscription_id`, `session_id`, `run_id`). `runtime.outcome`, `runtime.state`, and `runtime.subscriptionClosed` are Desktop control notifications, not new runtime events.

**Rationale**: Runtime event types, payloads, sequence, and `SCHEMA_VERSION` are already the shared contract used by Web, CLI, checkpoints, and inspection. Desktop is a consumer and must not create a second event vocabulary or re-emit the Event Bus.

**Alternatives considered**:

- Add Desktop correlation fields to `RuntimeEvent`: rejected because that is an event-schema change.
- Convert events into Desktop-specific view messages in the sidecar: rejected because presentation adaptation belongs to the client and would drift from Web.

## Decision 5: Add minimal Host resumed-interaction and portable-storage seams

**Decision**: Add an additive async context manager to `LoopPlaneHost`, named during implementation consistently with the approved contract (planned shape: `resume_session(session_id, on_event, *, on_approval=None, working_scope=None) -> AsyncIterator[Session]`). It:

1. acquires the existing host active guard;
2. discovers and activates the persisted principal through existing host/controller summary data;
3. calls `RuntimeController.resume(session_id, working_scope=...)`;
4. attaches the reviewer, binds the existing `RunSink`, and invokes the existing replay attach behavior;
5. yields the existing `Session` handle for `submit`, `cancel`, `answer_approval`, and `answer_question`;
6. unbinds the sink and releases active ownership on every exit path.

`RuntimeController.resume()` receives an optional `working_scope`. `None` preserves the current `Path.cwd()` behavior exactly. Existing `LoopPlaneHost.resume(session_id)` remains a reconstruction/inspection operation with unchanged signature and behavior.

For portable recovery, add two default-unavailable `LoopPlaneHost` instance facades backed by an explicitly injected Desktop snapshot provider: `export_portable_snapshot(destination)` creates a consistent SQLite backup plus provenance-eligible referenced ArtifactStore copies in an empty staging directory, and `validate_portable_snapshot(source)` performs dedicated read-only validation for an inactive staged snapshot. Startup cannot use either instance facade because `LoopPlaneHost.__init__` immediately assembles normal stores, so `loopplane.host` also exports a non-instance `validate_active_generation(source, expectation, *, provider=None)` facade. It validates pristine absence or initialized current schema/SQLite ownership/artifact consistency under the already-held OS profile lock, uses a Host-owned injectable read-only provider for fault tests, constructs no Host/normal store, creates/mutates no filesystem entry, and returns no live storage handle/path. The sidecar never reads the live database/artifact roots or constructs checkpoint stores directly.

**Rationale**: The controller already reconstructs principal, model, context, history, decisions, and replay state; the missing interaction piece is a Host-owned composition of resume + bind + attach + existing `Session`. Backup also cannot satisfy Host-only integration by reaching into private SQLite/ArtifactStore paths, so snapshot/export validation must be Host-owned, explicitly injected, default-unavailable, and independently testable.

**Alternatives considered**:

- Call controller methods directly from the sidecar: rejected as a Host boundary violation.
- Call `host.resume()` then `host.session()`: rejected because `session()` creates a new session rather than continuing the persisted one.
- Persist raw workspace paths in checkpoint metadata: rejected because it changes the record contract and leaks private local topology.

## Decision 6: Use one generated per-profile principal and private workspace bindings

**Decision**: A Desktop profile owns one opaque UUID principal generated at first creation and retained across restart, backup, and restore. It is never supplied or selected by the renderer. Before reading pointer/proof/journals, creating any store, or constructing a Host, the sidecar canonicalizes the profile root and acquires a generation-external OS-backed exclusive `device-private/profile-owner.lock`. POSIX uses a process-held exclusive advisory file lock; Windows uses an exclusive handle/byte-range lock without sharing. Canonical aliases map to one lock identity. Contention returns public-safe `busy` and constructs zero Host; process crash relies on kernel release, while unsupported/remote/ambiguous locking fails closed. PID/text/timestamp or stale lock-file presence is diagnostic only and never authority. The same profile owns portable Desktop Projects—safe grouping metadata with opaque ID, label, optional Workspace Reference, and principal-owned session membership; one session belongs to at most one project in V1, and deleting a project never deletes sessions or workspace data.

The profile separates:

- **portable safe state**: schema version, principal, opaque workspace references, safe labels/status, pane preferences, and backup metadata;
- **device-private state**: `workspace_reference -> canonical local path + revalidation metadata` plus the non-portable ownership-lock file, stored in a profile-root `device-private/` sibling outside every portable Profile Generation, excluded from backup and every renderer/protocol/event/checkpoint projection, and never revived by generation switch or rollback.

Native folder selection is main-owned. The trusted sidecar canonicalizes and validates the selected path, creates or relinks an opaque workspace reference, and projects only `{id, label, availability, actions}`. Interactive resume passes a path to the Host only after current revalidation succeeds. Because revalidation persists safe availability and private validation timestamps/state, explicit `workspace.revalidate` is an all-writer Profile-Mutation-Lease operation; create/resume may perform the same check inside their existing mutation lease, and backup/restore ownership blocks any separate revalidation write. Missing or changed bindings leave history and audit readable but block workspace-dependent submission until explicit relink.

**Rationale**: Existing `WorkspaceContext` and checkpoint metadata already represent only safe identifiers/labels; `RunContext.working_scope` is the actual tool scope. Keeping path bindings private preserves this separation.

**Alternatives considered**:

- Store paths in renderer/localStorage: rejected because renderer state is not an authorization boundary.
- Store paths in checkpoint records: rejected because it changes durable schema and makes portable backups disclose topology.
- Let renderer submit arbitrary paths/principals: rejected because it enables impersonation and unrestricted scope selection.
- Use a PID/timestamp/stale-file convention instead of a kernel-held lock: rejected because crash and alias races can produce two authoritative sidecars.
- Acquire the lock after recovery or Host construction: rejected because a second process could already read/mutate authority or initialize stores.

## Decision 7: Enforce one profile-wide interactive lease while sharing read projections

**Decision**: Inside the already-held cross-process Profile Ownership Lock, the owning sidecar maintains one transient in-process `DesktopInteractionLease` for the entire profile. The lease is acquired before a new or resumed interactive session becomes writable, identifies the trusted session/run owner, and is released on terminal outcome, cancel, context exit, EOF, or shutdown; a process crash releases the outer OS ownership so a later process must rerun full recovery before creating a new lease. A second submission or sidecar process is rejected before `Session.submit()` or model invocation.

The renderer keeps multiple panes, but a session has one shared projection/subscription. Opening the same session focuses its existing pane; forking creates a new session. Non-owner panes retain independent in-memory drafts/focus/inspection state and may read history/audit/settings while one pane is interactive. Unsent drafts are intentionally excluded from profile persistence and backup.

**Rationale**: `LoopPlaneHost._active` is a required second guard but does not provide the pane-aware conflict information needed for Desktop UX. A profile lease prevents races without introducing multiple hosts or distributed scheduling.

**Alternatives considered**:

- One host per pane: rejected because it defeats the single-active Desktop boundary and introduces cross-host state races.
- Renderer-only lease: rejected because a compromised or stale renderer could bypass it.
- Disable all other panes during a run: rejected because read-only comparison and inspection are core cowork value.

## Decision 8: Extract a transport-neutral presentation host, not a shared HTTP client

**Decision**: Refactor Web presentation around a narrow internal `CoworkPresentationHost` interface covering session CRUD/history/fork, run lifecycle, approval/question answers, projections, inspection, capability actions, and Desktop-only profile operations where available. `WebPresentationHost` adapts the existing `ApiClient + SessionTransport`; `DesktopPresentationHost` adapts typed preload operations. The existing Web outward `/v1` and generated contracts remain unchanged.

Shared UI owns shell, reducer, message list, dialogs, settings/inspection composition, accessibility, locale, theme, and safe loading/error states. Web and Desktop remain thin composition roots. Capability absence is explicit so Desktop-only operations do not appear in Web and unavailable host features remain read-only/hidden rather than fabricated.

**Rationale**: `apps/web/src/App.tsx` already injects `SessionTransport`, but sessions, settings, cost, and inspection still depend directly on `ApiClient`. Pretending the sidecar is HTTP would couple Desktop to Web transport and still not support profile/pane operations.

**Alternatives considered**:

- Copy the Web app into Desktop: rejected because behavior and accessibility would drift.
- Make Desktop start/call the Web API: rejected because it introduces a local network service and the wrong lifecycle/security boundary.
- Add Desktop methods to the public Web transport contract: rejected because that would change an existing outward contract.

## Decision 9: Keep turn audit durable but intentionally bounded

**Decision**: Add a read-only Host facade for a `TurnAuditEntry` projection derived from existing checkpoint records. V1 audit identifies logical submitted turns by stable checkpoint sequence, ordinal, timestamps where already durable, state (`completed` or `interrupted`), termination reason, and recorded turn count when available. It excludes prompt text, assistant text, tool input/output, artifact content, approval/question answers, diagnostics, raw errors, and principal/path data.

V1 does not claim per-runtime-event audit fidelity. Approval/question transitions and every model sub-turn are not all durable in current checkpoints; adding them would require a new record/read-model contract beyond 078.

**Rationale**: A checkpoint-derived read model survives restart, is stable, and avoids a second event source. Sidecar-maintained event copies would be incomplete and could leak payloads.

**Alternatives considered**:

- Archive raw runtime events as audit: rejected because it duplicates the event stream and may contain private payloads.
- Treat Web replay data as audit: rejected because replay is a transport cache, not the canonical Desktop session store.
- Add new checkpoint audit records: rejected because record-schema changes are outside 078.

## Decision 10: Use existing SQLite checkpoints plus referenced artifacts for Desktop durability

**Decision**: The Desktop sidecar explicitly configures `StorageConfig` under the active profile generation with `checkpoint_backend="sqlite"`. Existing `SqliteCheckpointStore`, `ArtifactStore`, capability store, and Host configuration are reused; the global/default Host behavior remains unchanged because only Desktop startup opts in.

A fresh pristine generation declares `checkpoint_state=absent_uninitialized` and `artifact_state=absent_uninitialized`. Pre-Host recovery validates only that the SQLite and artifact payloads are absent; the sidecar does not open/create SQLite, instantiate ArtifactStore, or duplicate schema initialization. After pointer/proof/receipt authority is valid, first normal Host durable use lets the existing checkpoint/artifact owners create their stores. Any unexpected pre-Host payload fails locked. Restored and non-pristine generations use dedicated read-only validation before Host construction.

The default startup model reuses the existing credential-free model selection behavior and trusted environment/provider construction; credentials remain outside the renderer and backup. The protocol advertises honest model/capability availability.

**Rationale**: SQLite is already a supported standard-library-backed checkpoint option, provides a single durable session database suitable for a local profile, and avoids a new dependency. `StorageConfig` already wires artifacts and capability settings under a host-chosen root.

**Alternatives considered**:

- Leave Desktop storage disabled: rejected because sessions could not survive restart.
- Introduce a new Desktop session database: rejected because checkpoint ownership already belongs to the controller.
- Change `StorageConfig` defaults globally: rejected because all new behavior must be Desktop-local and default-preserving.
- Make the sidecar pre-create or introspect live SQLite/ArtifactStore before Host authority: rejected because it duplicates existing store ownership and contradicts proof-before-Host; explicit pristine absence resolves bootstrap without reach-through.

## Decision 11: Export a versioned allowlist and restore by generation pointer

**Decision**: Use Python standard-library `zipfile`, `json`, `hashlib.sha256`, `tempfile`, `pathlib`, `os`, and `ctypes`; never call `extractall()`. Restore publication uses explicit platform-scoped guarantees rather than pretending they are equivalent. POSIX supported local filesystems use regular-file and directory `fsync`, same-filesystem `os.replace`, and both parent-directory `fsync`s for the exercised physical-power-loss claim. The required Windows artifact accepts only documented supported local filesystems (initially local NTFS/ReFS), uses regular-file `FlushFileBuffers`, same-volume `MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` or an equivalently documented write-through replace, and post-move reopen/current consistency validation for a process/application-crash guarantee. It does not claim undocumented directory-handle flush semantics or sudden physical-power-loss persistence of both parent-directory entries. Unsupported remote/volume/API behavior fails before pointer mutation, and Stage B must explicitly accept the Windows limitation.

A canonical `manifest.json` declares format version, profile compatibility, creation time, entry count/size limits, and each exact POSIX-relative entry with uncompressed size and SHA-256. The initial allowlist includes:

- portable profile identity, Desktop Projects, and safe preferences with unsent drafts removed;
- opaque workspace references/labels marked `relink_required`;
- a Host-owned consistent SQLite checkpoint snapshot containing full session history;
- only checkpoint-referenced, provenance-eligible existing Gateway ArtifactStore outputs copied by the Host facade after regular-file/no-follow/root/identity checks;
- metadata-safe audit data when it is not derivable at restore time.

It excludes provider credentials/tokens, private capability configuration selected by the contract, recursive/direct collection of arbitrary workspace contents, device-private path mappings, unsent drafts, raw internal logs/errors, caches, PIDs, active leases, pending protocol state, uploads not represented by eligible durable Gateway artifacts, and unrelated artifacts.

Full session and eligible artifact content is preserved losslessly. The creation flow explicitly warns that the archive is not application-encrypted and may retain user-, model-, or tool-produced credentials, paths, workspace excerpts, and other sensitive content; unsent drafts are excluded. The guarantee is therefore: LoopPlane-owned secrets/configuration/private path mappings and recursive/direct workspace collection are excluded; sensitive authorized conversation/artifact content is not silently guessed or redacted.

One Profile Mutation Lease is the common in-process writer gate for active-generation and generation-external profile state. Backup acquires it before Host snapshot/profile serialization and holds it through archive finalization. `restore.validate` atomically reserves it before staging and retains it until commit/cancel/expiry/shutdown cleanup. While either operation owns it, competing session create/rename/star/fork/delete, interactive open/submit/answer, Project/workspace/capability/profile mutations, backup, and restore fail before Host/profile dispatch. Only the reservation-owning restore transition and bounded cancel/release/shutdown teardown may pass, and teardown starts no new durable work. Validation then checks format/limits/paths/links/duplicates/case-fold and normalization collisions/compression method/size/hash/schema into same-volume staging through the Host-owned read-only validation facade.

Before either initial bootstrap or restore pointer publication, one fail-closed platform-scoped primitive completes the applicable publication protocol, reopens the final generation, and validates its publication-time inventory/schema/SQLite/artifacts. It emits a canonical immutable Generation Publication Receipt object/digest bound into pointer, journals, and Active Generation Proof. That receipt records the publication event and accepted durability scope; it is not a permanent content hash because the active generation becomes mutable as checkpoints/artifacts/profile state change. Startup validates receipt lineage and current profile/SQLite/artifact consistency without comparing mutable files to publication-time hashes. Fresh bootstrap writes/rereads its receipt-bound bootstrap proof before the exact pointer and constructs no Host until pointer/proof/receipt lineage plus current generation validation match; a crash between proof and pointer can complete only those embedded pointer bytes on an otherwise pristine profile.

Commit uses two complete copy-on-write journal slots, `restore-journal-a.json` and `restore-journal-b.json`, plus an independent `active-generation-proof.json`. Before pointer replacement, both checksummed slots are written/reread through the applicable platform durable-write primitive with exact previous pointer/proof preimages, candidate pointer, canonical publication receipt, restore/archive IDs, and old/new generation IDs. A transition replaces only the older slot so another full preimage remains valid. After candidate pointer publication, the sole `DesktopRuntimeOwner` constructs/readiness-checks a fresh candidate-generation `LoopPlaneHost`, closes and atomically installs it only on success, and only then publishes a checksummed active proof matching the exact candidate pointer and receipt. That proof is the positive startup authority; journal `verified` is written afterward and slots are cleaned one at a time.

A definitive pre-proof failure closes the candidate and uses either valid journal slot to restore the exact previous proof/pointer pair plus a usable previous-generation Host before releasing mutation ownership. If proof replace/flush may have taken effect but the process has no successful reread/acknowledgement, it performs no rollback, cleanup, binding deletion, or further recovery-record mutation; it stops dispatch, retains both journals, and requires startup to adjudicate the proof. Startup before Host construction keeps a matching pointer/proof/receipt, otherwise rolls back from one valid full-preimage slot or fails locked. A torn/truncated/corrupt/missing individual slot is tolerated by its peer; both unavailable before proof never authorize candidate activation. Restored `relink_required` references are rejected before any binding lookup, so identical-ID pre-restore bindings are ignored until explicit relink and cleaned only after proof authority; rollback may continue using previous-generation binding state.

Backup/restore internal causes are not renderer/RPC categories. A single exhaustive mapping selects an existing RPC code/category plus exact retryability, required-or-absent shared recovery enum, and fixed allowlisted localization key: unsafe/integrity/limit causes use `unsafe_input`; incompatibility uses `incompatible_protocol`; profile contention uses `busy/wait`; insufficient space uses retryable `unavailable`; durability uses `durability_unsupported/contact_support`; publication uses one of the two `publication_failed` variants; exact rollback uses retryable `publication_failed`; cancellation uses `cancelled`; and the explicit unknown fallback is exactly `-32603 internal_failure`, `retryable=true`, `restart_runtime`, and `desktop.error.internal_failure`.

**Rationale**: Replacing a non-empty profile directory is not portably atomic. A generation pointer provides a small atomic publication point and preserves rollback. Content redaction cannot be both reliable and lossless. A single cause-to-wire table prevents contract drift or accidental publication of internal recovery labels.

**Alternatives considered**:

- Metadata-only backup: rejected by the maintainer because the selected behavior is complete, honest recovery.
- Heuristic path/secret redaction: rejected because it can miss secrets, corrupt history, and create a false guarantee.
- Encrypted backup in 078: deferred because it requires a new cryptographic dependency and password/key lifecycle.
- Direct in-place extraction: rejected because partial failure can destroy the active profile.
- Treat restore validation as read-only/no reservation: rejected because staging and token creation are durable side effects that must exclude concurrent interaction/profile mutation.
- Activate a candidate without durable restore evidence and live Host handover: rejected because a crash after pointer replacement cannot otherwise distinguish verified completion from an incomplete restore, and a constructor-bound old Host would continue reading/writing the previous generation after the pointer changed.
- Rewrite one `restore-journal.json` in place or delete it as the sole verification marker: rejected because a torn/truncated/missing state transition can destroy the only exact previous-pointer/proof preimage. Redundant copy-on-write full-preimage slots are retained until an independent matching active proof is durable.
- Claim Windows parent-directory physical-power-loss durability from directory-handle `FlushFileBuffers`: rejected because the reviewed Microsoft contracts do not document that guarantee for unprivileged directory metadata. 078 instead makes the narrower documented Windows process/application-crash claim, rejects unsupported/remote volumes, reopens and validates current state fail closed, and requires explicit Stage B acceptance of the remaining sudden-power-loss limitation.

## Decision 12: Pin PyInstaller as a build-only tool and prove isolated artifacts

**Decision**: Keep the declared dependency set unchanged and use Stage A, two serial Stage-B submitted reviews for implementation authorization, plus a third post-implementation Stage-C delivery review before freeze/package/smoke. Stage A narrowly authorizes creation of `apps/desktop/sidecar/pyinstaller-build.in` containing only `pyinstaller==6.21.0`, candidate `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt` for Python 3.12 on `x86_64-pc-windows-msvc` with the exact `uv pip compile --generate-hashes --only-binary :all:` command, and bounded evidence. T002's bootstrap review binds design, `pyproject.toml`, `uv.lock`, and that candidate lock but authorizes only T003 RED verifier tests plus T004 verifier/dependency-manifest/root-lock materialization while ADR 0015 remains Proposed. T004 creates every complete final root/Web/Desktop/shared manifest field—including dependency/workspace/script/entrypoint/exports/files/package metadata—before generating the sole root lock. T005's distinct final submitted review is invoked with both immutable T002/T005 locator tuples, independently refetches both complete trees, and accepts only an exact path/type/Git-mode/blob/add/modify/delete diff limited to the T003 verifier test, T004 verifier, four final manifests, root lock, bounded bootstrap evidence, and deletion of the two app-local locks. It then binds T003/T004 outputs, both Python authority files, the exact Desktop extras allowlist (`anthropic`, `gemini`, `mcp`, `net`, `oauth`, `openai`), the PyInstaller lock, those final manifests, root lock, and app-local-lock absence; only then is the ADR accepted and product work authorized. T006+ treats all accepted manifest/lock bytes as immutable; any later package metadata need returns to T004 and a new T005 before install/build. T005 deliberately does not claim future implementation bytes. After T006–T089, T090 delivery mode receives explicit T002/T005/T090 locator tuples, independently refetches all three authorities, proves same PR and pairwise-distinct IDs, reruns the T002-to-T005 allowlist, and rederives prior bundles/locks without trusting ADR/evidence. The third review then binds actual product/verifier/wrapper/workflow/PyInstaller-spec/packaging/accessibility/smoke source and materializes an exact reviewed-tree source snapshot before the first freeze/package/artifact smoke.

The verifier's GitHub authority seam is explicit and fail closed. Immutable inputs identify shared owner/repository/pull-request/expected-approver values plus T002 for bootstrap, T002+T005 for final, or T002+T005+T090 review-ID/expected-commit pairs; prior locators never come from ADR/evidence/config, mutable refs, or list/search APIs. The only credential source is short-lived `LOOPPLANE_STAGE_B_GITHUB_TOKEN` confined to an isolated verifier process/step. It never falls back to `GH_TOKEN`, `GITHUB_TOKEN`, `gh auth`, git credentials, evidence text, or persisted login state. Singular REST calls fetch the pull request author, every required review, exact git commits, complete recursive trees with `truncated=false`, and exact blobs using the pinned API version. `user.type=User` plus `author_association` in OWNER/MEMBER/COLLABORATOR proves repository association, while exact expected-login equality and case-insensitive inequality from PR `user.login` reject unexpected reviewers and self-approval. Final/delivery modes rerun the exact T002-to-T005 full-tree allowlist and independently rederive prior authority. Missing/insufficient credentials, stale/substituted locators, full-tree-diff violation, HTTP/rate/timeout/redirect/API-shape failure, truncated tree, expected-actor/PR-author/commit mismatch, or response inconsistency emits no descriptor and authorizes no ADR/build action; token/header/raw response content is never logged. CI declares only `contents: read` and `pull-requests: read`, injects `${{ github.token }}` only into the verifier step, and does not use `pull_request_target` to bypass fork permissions. After descriptor emission, package/freeze/smoke run in a separate step whose wrappers and external descendants reject or scrub `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN`.

**Reference**: GitHub REST documents the singular review response fields and the content-addressed commit/tree/blob resources used here; recursive tree responses can explicitly report `truncated=true`, which this bounded verifier rejects rather than silently accepting an incomplete inventory: <https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#get-a-pull-request>, <https://docs.github.com/en/rest/pulls/reviews?apiVersion=2022-11-28#get-a-review-for-a-pull-request>, <https://docs.github.com/en/rest/git/commits?apiVersion=2022-11-28#get-a-commit-object>, <https://docs.github.com/en/rest/git/trees?apiVersion=2022-11-28#get-a-tree>, and <https://docs.github.com/en/rest/git/blobs?apiVersion=2022-11-28#get-a-blob>. GitHub Actions documents `pull_request_review` with `types: [submitted]`, exposes `github.event.review`, and sets `GITHUB_SHA`/`GITHUB_REF` to the PR merge branch rather than necessarily the reviewed commit, so the delivery job must use and revalidate `github.event.review.commit_id`: <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_review>.

`scripts/verify-desktop-stage-b.ps1` final mode refetches T002/T005, enforces their complete-tree allowlist, and fetches exact T005-reviewed bytes for the PyInstaller lock, `pyproject.toml`, and `uv.lock` into a fresh absolute-path accepted-input snapshot; delivery mode later refetches all three reviews, revalidates those bytes, and materializes the exact T090-reviewed implementation tree into a separate no-link read-only source snapshot. After the tokenized verifier exits, token-free `scripts/build-desktop-sidecar.ps1` derives a hashed production requirements snapshot from those accepted Python authorities with exactly the six extras, passes only accepted snapshot paths to one strict wheel/hash `uv pip sync`, verifies the resulting environment, and freezes only delivery-reviewed `src/loopplane` plus sidecar source through a hardened spec. Replacing/restoring the worktree lock after initial verification cannot affect `uv`; a focused test proves this. Bare/global `pyinstaller`, direct install, `uv tool run`, ambient `PYTHONPATH`, PATH-injected executables, incomplete PyInstaller-only environments, and copied variants are prohibited. The guarantee covers repository/worktree mutation and accidental drift, not a malicious process already running as the same OS principal with access to private build memory/directories.

Establish one deterministic first-party JavaScript install/build graph so Desktop can bundle shared Web presentation without sibling `node_modules`. The final Stage-B record includes the exact root-lock digest. Token-free `scripts/build-desktop-package.ps1` accepts only the preceding verifier's descriptor, builds from the T090-reviewed source snapshot in a fresh build root, installs only the T005-reviewed root/app/shared manifest and lock bytes there, confirms both app-local locks are absent, and runs `npm ci`/lifecycle/build/electron-builder only in that snapshot with GitHub token variables removed from every descendant environment. Replacing/restoring the checkout lock after verification cannot alter the install. Emit renderer, Electron main, and preload artifacts explicitly; align package entrypoints/files and sidecar `extraResources`. Required CI and maintained docs use the package wrapper, whose sidecar step delegates only to the sole sidecar wrapper.

Required Windows CI separates determinant coverage from delivery authority. Path-filtered `push`/`pull_request` source gates cover `.github/workflows/desktop.yml`, root `package.json`/`package-lock.json`, `pyproject.toml`, `uv.lock`, `apps/desktop/**`, `apps/web/**`, `packages/cowork-presentation/**`, `src/**`, `tests/**`, all four delivery scripts, ADR 0015, and the complete 078 spec directory, but do not package before Stage C. A separate `pull_request_review` `submitted` delivery job takes T090 PR/review-ID/commit locators from the immutable event, T002/T005 review IDs and commit SHAs from four maintainer-controlled non-secret repository variables, and expected approver only from `LOOPPLANE_DESKTOP_EXPECTED_APPROVER`. Its isolated tokenized verifier step refetches all three API authorities, rejects event/API disagreement, proves same PR/pairwise-distinct IDs/the T002-to-T005 full-tree allowlist, and emits a non-secret descriptor; a separate token-free step runs the package wrapper against that exact reviewed source, delegates freeze only to the sidecar wrapper, and executes the external-CWD `-Scenario all` smoke.

The built-artifact smoke has one normative CLI that first copies the whole `apps/desktop/release/win-unpacked` artifact tree into a fresh GUID-named `%TEMP%` run root, resolves `LoopPlane.exe` only from that copied tree and the smoke script to an absolute checkout path, then changes to the external run root before invoking the script with `-AppExecutable $appExecutable -ScratchRoot $scratchRoot -EvidencePath $evidencePath -Scenario all`. The script also accepts `happy`, `missing-sidecar`, `corrupt-sidecar`, and `incompatible-sidecar`; it canonicalizes and rejects an executable, scratch root, evidence path, profile, or inherited working directory located inside the checkout, creates fresh per-scenario state, clears `PYTHONPATH`/`NODE_PATH`, restores any temporarily altered copied artifact, and writes bounded non-secret evidence. Interaction uses built-in Windows .NET UI Automation and the actual Electron/Chromium accessibility provider—not an assumed DOM-to-AutomationId mapping. Packaged-smoke mode enables Electron accessibility after readiness and before BrowserWindow creation, then the same visible controls expose seven fixed non-localized Name/ControlType pairs: runtime status/Group, new session/Button, prompt/Edit, submit/Button, latest outcome/Group, session list/List, and runtime diagnostic/Group. The driver preflights exactly one of each pair before interaction, submits `loopplane packaged smoke`, requires exact terminal marker `loopplane-packaged-smoke-ok`, closes/relaunches through normal window automation, and observes the persisted session. A packaged-only bounded launch mode selects an external scratch profile and the existing credential-free `ScriptedModel`; it exposes no raw path/RPC/IPC/process capability. No Playwright/Appium/WinAppDriver dependency, AutomationId/localized-text fallback, CDP/DevTools/remote-debugging port, DOM injection, or local listener is introduced. Packaging contract tests prove successful external-CWD invocation and direct checkout-CWD rejection plus every other checkout-path rejection. This demonstrates protocol initialize, GUI startup, one credential-free session, terminal outcome, shutdown/restart durability, no local listener/orphan, and 10-second public-safe diagnosis with profile preservation without source-tree fallback. Evidence is reported only for platforms actually exercised; signing, notarization, publishing, and release remain out of scope.

**Reference**: Electron documents that `app.setAccessibilitySupportEnabled(enabled)` must be called after the `ready` event and that forced accessibility-tree rendering has a performance cost, supporting the packaged-smoke-only `app.whenReady()`/pre-BrowserWindow placement: <https://github.com/electron/electron/blob/main/docs/api/app.md> and <https://github.com/electron/electron/blob/main/docs/tutorial/accessibility.md>.

**Rationale**: The current Desktop package references shared Web source whose dependencies are not present in the Desktop lockfile, uses TypeScript `noEmit`, and packages JavaScript paths that are not currently built. A source-only test cannot prove a distributable Desktop product.

**Alternatives considered**:

- Pin only the direct `pyinstaller` requirement or use `uv tool run --from`: rejected because transitive build packages may drift and the result is not a complete hash-constrained build resolution.
- Continue manual unpinned `pip install pyinstaller`: rejected because it is not reproducible.
- Retain bare/PATH/global PyInstaller or `uv tool run` beside the wrapper: rejected because it bypasses the accepted transitive lock and verifier.
- Hash the mutable worktree lock before and after sync: rejected because a replace/restore window can install a different self-hashed graph while both checks pass. The verifier instead materializes commit-derived accepted bytes, and `uv` consumes only the sealed descriptor paths; the stated threat model does not overclaim defense against a malicious same-principal process.
- Treat the existing Linux/apps-only workflow as package evidence: rejected because it neither builds the required Windows artifact nor exercises the external-CWD GUI smoke and misses non-app artifact determinants.
- Add PyInstaller to runtime dependencies: rejected because packaging tooling is not runtime behavior.
- Generate the root lock before the shared workspace manifest exists, or keep app-local lockfiles beside it: rejected because the reviewed/install graph would be incomplete or divergent. T004 creates every final manifest field first; T005 content-binds those immutable bytes, the sole root lock, and both app-lock absence records. Post-T005 script/entrypoint/files metadata edits are equally rejected because they invalidate the reviewed install/build graph.
- Leave the artifact smoke as prose without a stable CLI: rejected because CI/local evidence would not be comparable or immediately runnable.
- Let the verifier discover ambient `gh`/git credentials or accept a token from evidence/CLI text: rejected because authority would depend on mutable machine state and credentials could leak into process listings, logs, or evidence. One explicit short-lived environment seam and minimum read permissions are required.
- Use DOM `id`/`data-testid`/ARIA values as presumed UIA `AutomationId`: rejected because Electron/Chromium does not guarantee that provider mapping. The actual packaged tree must expose and uniquely match the frozen Name/ControlType pairs.
- Skip artifact smoke: rejected because it would leave the primary Desktop delivery risk unverified.

## Decision 13: Require ADR 0015 and an explicit pre-implementation gate

**Decision**: Record the protocol, Electron trust boundary, Host resume/audit/portable-snapshot additions, cross-process profile ownership, profile/principal/project/workspace ownership, all-writer backup/restore reservation and durable-journal semantics, shared presentation boundary, and build-tool/package strategy in ADR 0015. Stage A may authorize only deterministic materialization of the two candidate build-lock files and bounded pre-gate evidence while ADR 0015 remains Proposed; it authorizes no commit/push/PR.

Stage B uses two serial submitted GitHub PR reviews for implementation authorization; Stage C adds a third post-implementation delivery review before freeze/package/smoke. Every review must have API-visible `state=APPROVED`, an API-controlled review ID/node ID, non-null `submitted_at`, exact `commit_id`, a non-bot owner/member/collaborator matching an immutable expected-approver login, and a login different case-insensitively from the singular PR author. Issue/PR comments, inline comments, pending reviews, PR-author self-approval, and editable review-body text are non-authoritative. T002's bootstrap review content-binds the design bundle, `pyproject.toml`/`uv.lock`, and candidate PyInstaller lock and authorizes only T003/T004 while ADR 0015 remains Proposed. T004 creates all three verifier modes and the complete root/app/shared dependency manifest graph before the sole root lock, with no install/build. T005 requires immutable T002/T005 locator tuples and a distinct new submitted review over that pre-implementation post-materialization tree; it independently refetches both complete trees and requires their exact full-tree diff to contain only the T003 verifier test, T004 verifier, all dependency manifests, root lock, bounded bootstrap evidence, and app-local-lock deletions. Its canonical inventory includes design/contracts/ADR, T003/T004 outputs, all dependency manifests, root lock, and explicit app-local-lock absence. T005 derives both lock digests, changes ADR status, and writes the identical final API identity/commit/tree/bundle/PyInstaller-lock/root-lock field set in ADR/evidence. T006+ source work requires final-mode verification, but T005 does not claim future source. T090 requires immutable T002/T005/T090 locator tuples and a third distinct review over the post-T089 implementation commit; it independently refetches all three authorities, proves pairwise-distinct IDs and the T002-to-T005 allowlist, binds actual artifact determinants, and materializes exact reviewed source before package execution. It writes a separate evidence-only delivery field set; the tokenized verifier then exits before token-free wrappers/build tools run. A missing/dismissed review, expected-actor/PR-author/commit/review-ID/bound-artifact/source/Python-authority/lock drift requires a new applicable submitted review. These gates authorize only scoped local 078 work; they do not authorize event/checkpoint/Gateway/default/Web outward-contract changes, new declared dependencies, release, signing, commit, or deployment.

**Rationale**: 078 adds a private process protocol, new public Host facades, a Desktop profile durability boundary, and backup semantics. These are load-bearing even though they preserve existing runtime contracts.

**Alternatives considered**:

- Treat 078 as UI-only: rejected because the current Desktop bridge cannot safely support interactive sessions or durable local work.
- Require acceptance of a not-yet-generated transitive lock: rejected because it creates a circular prerequisite; the narrow Stage A and full Stage B separate materialization from implementation authorization.
- Accept an unverified textual approval reference or self-authored evidence: rejected because it does not prove actor authority, approval liveness, or the exact reviewed artifact set.
- Treat issue/PR comments, inline comments, pending reviews, or PR-review body text as the artifact binding: rejected because those textual carriers can be edited; only the submitted review's stable identity/live `APPROVED` state/exact `commit_id` and the content-addressed review commit are authoritative.
- Accept any associated reviewer without fetching the PR author or requiring an expected login: rejected because it permits unexpected reviewers and cannot explicitly reject PR-author self-approval.
- Treat T005 as approval of future wrapper/workflow/smoke implementation: rejected because those bytes do not exist in the post-T004 commit; a distinct T090 delivery review binds the actual implementation before package execution.
- Compare only T005's enumerated canonical bundle: rejected because unauthorized product/workflow/path/mode changes outside the bundle could enter during T002's narrow authorization; final and delivery modes must diff the complete T002/T005 trees against one exact allowlist.
- Recover T002/T005 locators from ADR/evidence or the reviewed tree during delivery: rejected because those mutable records cannot root their own authority; all prior review/commit locators are immutable invocation inputs and are independently refetched.
- Give the package wrapper or build step the GitHub token: rejected because `npm` lifecycle scripts and external build descendants inherit process environments; only the verifier step receives the token, and all wrappers/tools run later under a scrubbed token-free environment.
- Bind only the lock digest: rejected because ADR/contracts/design or build mechanism could drift while preserving the same lock; commit/tree plus canonical bundle are required.
- Implement first and document later: rejected by Constitution I and the feature's own success criteria.
