# Contract: Desktop Profile, Workspace, Resume, and Turn Audit

**Status**: Proposed — implementation requires the 078 human gate.

## 1. Profile identity

- One Desktop installation profile has one generated `profile_id` and one generated opaque `principal_id`.
- The trusted sidecar generates both values at profile creation.
- `principal_id` is immutable for the life of the profile and is preserved by backup/restore.
- Renderer input, IPC, URL state, imported preferences, session metadata, and backup destination cannot choose or replace the principal.
- All Host list/read/mutate operations are scoped to that principal.
- A session whose principal does not match the active profile is returned as enumeration-safe `not_found`, not as cross-principal metadata.

This local identity is not remote authentication and creates no multi-user or account semantics.

## 2. Profile storage layout

The Desktop owner chooses one OS-appropriate profile root. The root contains:

```text
<desktop-profile-root>/
├── active-generation.json       # Small atomically replaceable pointer
├── active-generation-proof.json # Checksummed proof for the only normal-open pointer
├── generations/
│   ├── <generation-id>/
│   │   ├── profile.json         # Portable safe identity/projects/preferences/references; no drafts
│   │   ├── checkpoints.sqlite3  # Existing SQLite checkpoint backend
│   │   └── <session-id>/artifacts/**
│   └── ...
├── restore-journal-a.json       # Complete checksummed previous pointer/proof preimage
├── restore-journal-b.json       # Redundant COW peer; both exist only during recovery/publication
├── device-private/
│   ├── profile-owner.lock       # Generation-external OS lock target; file contents are not authority
│   └── workspace-bindings.json  # Never portable or renderer-visible
├── staging/                     # Restore/backup work; never active
└── private-diagnostics/         # Optional bounded diagnostics, excluded from renderer/backup
```

The exact filenames may be normalized during implementation, but ownership and inclusion rules are binding.

Rules:

- Desktop opts into existing `StorageConfig(..., checkpoint_backend="sqlite")` under the active generation. Global/default Host storage behavior is unchanged.
- Before reading pointer/proof/journals, creating stores, or constructing a Host, the sidecar canonicalizes the local profile root and acquires one non-blocking OS-backed exclusive lock on the generation-external `device-private/profile-owner.lock`. Supported POSIX uses a process-held exclusive advisory file lock; Windows uses a process-held exclusive handle/byte-range lock with no sharing. Unsupported/remote lock semantics fail closed. A second process receives public-safe `busy` and constructs zero Host; kernel release after crash permits one later owner. Lock-file contents, PID text, timestamps, and stale file presence are diagnostic only and never authority.
- Before an initial or restore generation can be referenced, the trusted durability owner completes the platform-scoped publication protocol. POSIX local filesystems flush regular files and generation directories, perform a same-filesystem rename, and `fsync` both parent directories with a physical-power-loss claim. The required Windows artifact accepts only documented supported local filesystems, uses regular-file `FlushFileBuffers`, a same-volume write-through move/replace, and post-move reopen/current consistency checks with a process/application-crash claim; it does not claim undocumented parent-directory physical-power-loss persistence. Unsupported/error outcomes reject before pointer mutation, and Stage B explicitly accepts the Windows limitation.
- Publication creates a canonical immutable Generation Publication Receipt bound into pointer/proof/journals. The active generation becomes mutable after Host construction; startup validates receipt lineage plus current profile schema, SQLite integrity/ownership, and artifact consistency, never equality with publication-time file hashes.
- Fresh profile bootstrap writes/rereads a receipt-bound `bootstrap` Active Generation Proof before its exact pointer and constructs no Host until pointer/proof/publication-receipt lineage and current-generation validation match. Its only pre-Host store state is a declared zero-session `absent_uninitialized` checkpoint/artifact state: validation proves the SQLite file and artifact payload are absent and never opens/creates them; normal Host/checkpoint/artifact owners create them on first durable use. A pristine proof-without-pointer crash may complete only the embedded exact pointer; every other mismatch fails locked.
- Existing checkpoint and artifact owners remain unchanged.
- Existing capability settings are not blindly copied into portable profile data; V1 backup excludes the capability store because it can contain private endpoints/configuration.
- Unsent pane/composer drafts are renderer-transient and are excluded from `profile.json`, restart durability, and backup.
- Startup validates the exact pointer against `active-generation-proof.json`, validates the canonical publication receipt and current mutable generation, and independently validates both journal slots before normal Host construction. A matching pointer/proof/receipt lineage is the only normal-open authority; an unproved candidate rolls back from either checksum-valid full-preimage slot, while no matching proof and no unambiguous valid slot fails locked with zero Host construction.
- Both journal slots reread validly before candidate-pointer publication. State changes COW-replace only the older slot via same-directory temp write, regular-file flush, platform write-through replace, and post-replace validation; POSIX additionally `fsync`s the parent directory. A single torn/truncated/corrupt/missing slot is recoverable from its peer until a matching candidate proof is authoritative.
- Startup opens only the generation named by a valid independently proved or exactly journal-recovered pointer. Orphan staging/generations are not activated implicitly, and no retained generation is selected merely because it exists or previously opened.
- Device-private Workspace Bindings remain outside every generation. Every restored Workspace Reference is forced to `relink_required` before candidate Host composition, and that state hard-blocks any binding lookup; an old identical-ID binding is ignored until explicit relink. It may be retained only as rollback data until candidate proof authority, then quarantined/deleted safely.
- A generation that cannot be opened permits previous-generation recovery only from a checksum-valid, lineage-consistent journal's exact previous pointer/proof preimage. Without that authority, startup fails locked with zero Host rather than selecting a prior directory.

### Runtime owner and generation handover

Only the sidecar holding the profile's OS-backed ownership lock may own one `DesktopRuntimeOwner` containing the only live `LoopPlaneHost` and a factory/configuration that composes a Host for one exact Profile Generation. RPC method dispatch reads the Host only through this owner. Normal shutdown/EOF stops dispatch, tears down Host/stores, then releases the process-held lock; process crash relies on kernel release without claiming teardown ran. No second process may construct a Host while the first lock remains held.

- A Profile Mutation Lease reservation quiesces every Host/profile writer before restore publication; no session/interaction/Project/workspace/capability/profile/backup/restore mutation may race the handover. Read-only projections may continue only where the accepted snapshot/handover state machine explicitly permits them.
- After the candidate pointer is published, the owner constructs and readiness-checks a fresh Host rooted at the candidate generation. The old Host remains quiescent and receives no new requests.
- Candidate readiness must prove profile, Project, session/checkpoint, and eligible artifact stores open through normal composition. Only then may the owner close the old Host, install the candidate Host, and publish an Active Generation Proof matching the exact candidate pointer and canonical publication receipt; a later journal `verified` transition is cleanup evidence only.
- Failure before proof publication starts, or a definitive proof-write failure known not to have changed the target, closes the candidate, restores the exact prior proof/pointer bytes from either valid journal slot, and retains or reconstructs the previous-generation Host before the reservation is released. If proof replacement/flush may have taken effect but acknowledgement/reread is uncertain, the sidecar performs no rollback, cleanup, binding mutation, or further recovery-record write; it stops dispatch, retains both journals, and requires restart so startup alone adjudicates a matching proof versus exact journal rollback. Missing/ambiguous recovery evidence leaves the sidecar fail locked with zero Host dispatch.
- Startup handles pointer/proof/receipt/journal recovery before Host construction, validates the current mutable generation, then creates exactly one Host rooted at the independently proved or exactly journal-recovered pointer. After successful commit, every subsequent Host operation uses only the candidate generation.
- Device-private Workspace Bindings remain outside the generation swap. Restored `relink_required` state is enforced before binding lookup; identical-ID stale bindings are ignored and cleaned only after candidate proof authority, while rollback may continue using the previous generation's binding state.

## 3. Desktop Projects

A Desktop Project is profile-owned safe grouping metadata with an opaque ID, bounded label, optional Workspace Reference, and an ordered set of principal-owned session IDs.

- The sidecar generates project IDs; renderer input cannot choose an existing identity from another profile.
- One session belongs to at most one project in V1.
- Project create/list/rename/remove/session-assignment mutates only `profile.json` under the Profile Mutation Lease.
- Removing a project makes its sessions ungrouped and never deletes/renames sessions, checkpoints, artifacts, Workspace References/Bindings, or workspace contents.
- A project's optional workspace is a presentation/default association only; every interactive create/resume still requires current Workspace Binding validation.
- Projects and membership are portable; restored project workspace references remain `relink_required`.
- Projects own no runtime policy, principal, path, tool authorization, capability configuration, or interaction lease.

## 4. Workspace selection and binding

### Selection

1. Renderer requests the operation-specific `chooseAndBind` or `chooseAndRelink` facade method.
2. Electron main validates the sender and opens a native directory picker.
3. Cancellation returns `null`; no sidecar mutation occurs.
4. Main privately sends the selected absolute path to the sidecar. It is never returned to renderer or logged.
5. The sidecar canonicalizes and validates the directory under the current platform and existing tool/workspace policies.
6. On success, it atomically writes a device-private Workspace Binding and returns only a Workspace Reference projection.

### Validation

Before any new or resumed interactive session uses a workspace, the sidecar must revalidate in this order:

- reference belongs to current profile;
- reference availability is not `relink_required`; this hard pre-lookup denial ignores any device-private binding with identical restored profile/workspace IDs;
- binding exists;
- target exists and is a directory;
- canonical identity matches or a relink is required;
- link/reparse-point behavior is safe under the approved implementation;
- current process can access the scope;
- the scope is accepted by existing Host/tool workspace constraints.

A cached `available` label is insufficient authorization. The explicit `workspace.revalidate` RPC is a mutation: it must pass the Profile Mutation Lease writer gate and atomically persist the safe Workspace Reference availability plus private binding validation timestamps/state. Interactive create/resume may perform the same revalidation inside its already lease-gated mutation, but no revalidation write may occur while backup or restore owns/reserves the lease.

### Projection

Renderer-visible workspace data is limited to:

```json
{
  "id":"opaque-workspace-id",
  "label":"Safe label",
  "availability":"available",
  "actions":["open","relink","remove"]
}
```

It excludes absolute/canonical paths, parent hierarchy, usernames/home directories, volume identifiers, link targets, ACL details, validation exceptions, and device fingerprints.

### Relink and removal

- Relink preserves `workspace_id` only after validation confirms the user intends the existing reference to point to the newly selected directory.
- Failed/cancelled relink leaves the previous binding unchanged.
- After restore, every Workspace Reference begins `relink_required`; no path inference, name-based automatic binding, or identical-ID stale-binding reuse is allowed. A successful explicit relink atomically replaces/creates the current binding and changes availability; stale bindings may be quarantined/deleted only after candidate proof authority so rollback is not damaged.
- Removing a reference/binding never deletes local workspace contents or session history.
- History/audit remain readable without a binding; workspace-dependent submission is blocked with a relink action.

## 5. New and resumed interactive sessions

For runtime, checkpoint, and ArtifactStore operations, the sidecar uses only `LoopPlaneHost` public facades. It may directly own Desktop-specific profile/project/workspace-binding/restore-journal files defined by this contract, but it never reaches through Host into controller/checkpoint/artifact internals.

### New session

- Acquire the Desktop Interaction Lease.
- Resolve current profile principal and optional freshly validated workspace scope.
- Enter existing `LoopPlaneHost.session(...)` with sidecar-owned event/review callbacks, the trusted principal, and validated scope.
- Register the yielded existing `Session` under one opaque subscription.
- Submit/cancel/answer only through that `Session`.
- On every exit path, close the Host context and release the lease.

### Resumed session

A new additive Host context manager, planned as:

```python
@asynccontextmanager
async def resume_session(
    session_id: str,
    on_event: EventSink,
    *,
    on_approval: OnApproval | None = None,
    working_scope: Path | None = None,
) -> AsyncIterator[Session]: ...
```

must compose existing behavior as follows:

1. acquire the existing Host active guard;
2. find the session through the Host/controller summary seam and activate its persisted principal;
3. invoke `RuntimeController.resume(session_id, working_scope=working_scope)`;
4. attach reviewer, bind the existing `RunSink`, and use existing controller attach/replay behavior;
5. yield the existing `Session` abstraction;
6. unbind/release on normal completion, cancellation, callback failure, sidecar EOF/crash, or context exit.

`RuntimeController.resume` receives only this additive keyword parameter:

```python
async def resume(
    self,
    session_id: str,
    *,
    working_scope: Path | None = None,
) -> None: ...
```

Default-preserving rules:

- `working_scope=None` retains the existing `Path.cwd()` reconstruction behavior exactly.
- Existing `LoopPlaneHost.resume(session_id)` retains its current reconstruction/inspection signature and behavior.
- No checkpoint record field or schema is added for raw workspace paths.
- No sidecar code imports controller/checkpoint internals to simulate resume.
- Resume with a supplied scope occurs only after current Workspace Binding validation; otherwise Desktop remains read-only/relink-required.

## 6. Interaction lease

- The OS-backed Profile Ownership Lock is the outer cross-process guard; at most one owning sidecar and therefore at most one Desktop Interaction Lease exists for a canonical profile root across processes.
- A second process that cannot acquire profile ownership returns `busy` before pointer/recovery reads or Host construction; it cannot create its own interaction lease. Kernel crash release is covered before a later process may acquire.
- The in-process interaction lease is acquired before entering a new/resumed Host interactive context.
- A second request is rejected before `Session.submit` and before model/Gateway execution.
- Safe lease projection may include owner session/pane correlation and state; it excludes principal, path, PID, and raw internal task details.
- Approval/question/cancel operations are accepted only for the lease-owning subscription and exact pending request ID.
- Lease release is mandatory on:
  - normal terminal outcome and explicit interaction release;
  - cancel completion;
  - Host context exit or enter failure;
  - renderer/window shutdown after graceful teardown;
  - sidecar stdin EOF or shutdown;
  - callback/writer/notification overflow failure;
  - contained exception.
- `LoopPlaneHost`'s existing active guard remains a second enforcement layer.

Read-only session list/history/inspection/audit operations do not require the interaction lease. Restore requires the lease to be absent. Backup and restore use the separate Profile Mutation Lease: from backup lease acquisition through archive finalization, and from restore reservation through commit/cancel/expiry/shutdown cleanup, every session/Project/workspace/capability/interaction/backup/restore RPC capable of writing active-generation or generation-external profile state is rejected `busy` before Host dispatch. Only the owning restore commit/cancel and bounded system/interaction teardown may proceed; a safe teardown cannot start new durable work.

## 7. Host-owned projections and mutations

Desktop adapters may expose only existing Host-owned behavior plus the additive resume/audit facades accepted by ADR 0015.

- Session list/history/fork/rename/star/unstar/delete use Host public methods. Search is a bounded filter over Host-owned summaries/history. Project grouping is the separate Desktop profile operation defined above.
- Agent controls, capability settings/actions, cost/budget/context/upload/artifact posture use existing safe Host facades.
- Renderer draft choices are inputs to a turn and never replace accepted Host projection.
- Unknown/unavailable/unpriced values remain explicit.
- No Desktop component directly calls a tool adapter, model provider, controller private method, checkpoint writer, or Gateway adapter.

## 8. Turn audit projection

### Source

`LoopPlaneHost` exposes an additive read-only audit facade derived from existing checkpoint records. The facade may delegate to a store-owned read projection but may not create new records or copy the runtime event stream.

### V1 fields

Each `TurnAuditEntry` contains only:

- deterministic opaque audit ID;
- session ID;
- stable turn ordinal;
- checkpoint sequence;
- source-provided timestamp when durable;
- `completed` or `interrupted` state;
- bounded public-safe termination reason when represented by existing outcome metadata;
- recorded turn count when available.

### Exclusions

Audit never includes:

- prompt or assistant content;
- model/provider messages or usage payloads beyond a separately existing safe cost projection;
- tool names/arguments/results or artifact content;
- approval/question prompt/answer details;
- event payload copies;
- principal ID;
- workspace/archive paths;
- credentials, rules, configuration;
- raw internal error/traceback/diagnostics.

### Honesty boundary

V1 guarantees audit for logical submitted-turn checkpoint outcomes only. It does not claim a complete per-event, per-model-sub-turn, approval/question, or tool lifecycle because those transitions are not all durably represented by existing checkpoint records. Empty/unavailable audit fields remain `null`/unavailable rather than inferred.

### Ordering and pagination

- Entries are ordered by stable checkpoint sequence, then deterministic ID.
- Pagination uses an opaque cursor tied to the session/principal and stable ordering.
- Repeated reads are side-effect free.
- A fork's audit belongs to the forked session according to existing checkpoint lineage; the source is not mutated.

## 9. Host-owned portable snapshot and pre-Host generation validation

`LoopPlaneHost` exposes two additive, default-unavailable instance facades backed by an explicitly injected provider only in Desktop composition:

```python
async def export_portable_snapshot(
    destination: Path,
) -> PortableRuntimeSnapshot: ...

async def validate_portable_snapshot(
    source: Path,
) -> PortableSnapshotValidation: ...
```

The `loopplane.host` public package additionally exposes one non-instance startup facade for the period in which constructing `LoopPlaneHost` would already open/create normal stores:

```python
def validate_active_generation(
    source: Path,
    expectation: ActiveGenerationExpectation,
    *,
    provider: ActiveGenerationValidationProvider | None = None,
) -> ActiveGenerationValidation: ...
```

Rules:

- The `LoopPlaneHost` snapshot provider defaults to `None`; non-Desktop Host behavior and StorageConfig defaults remain unchanged.
- `export_portable_snapshot` requires a caller-owned empty staging directory, writes a consistent SQLite backup and copies only checkpoint-referenced eligible ArtifactStore entries, then returns a safe relative-path/integrity inventory. It never exposes the live database path/connection or ArtifactStore base path.
- V1 eligible artifacts are only existing Gateway `ArtifactStore` regular files with matching checkpoint reference and metadata, expected session/reference filename, active-generation-root containment, no symlink/reparse/special-file status, and stable before/after identity/size while hashing/copying.
- Artifact content origin is `gateway_tool_output`; it may contain workspace excerpts, paths, credentials, or other sensitive values and is covered by the backup disclosure. “Arbitrary workspace contents excluded” means no recursive/direct workspace-file collection beyond those already durable referenced artifacts.
- Missing/replaced/linked/unreferenced/metadata-inconsistent artifacts fail snapshot creation rather than producing a partial success.
- `validate_portable_snapshot` opens a staged, inactive snapshot through a dedicated read-only URI/query seam and validates schema/records/principal/artifact inventory without normal Host assembly, directory creation, schema initialization, or active-profile mutation.
- `validate_active_generation` is implemented in a Host-owned module and exported only through `loopplane.host`; the sidecar supplies the canonical generation root plus the proof/receipt-derived expected profile, principal, checkpoint state, and artifact state, but never receives a database connection, ArtifactStore root, record implementation, or storage handle.
- For `absent_uninitialized`, the active-generation facade performs no-follow absence checks only. For `initialized`, it uses dedicated read-only SQLite integrity/schema/ownership queries plus regular-file/no-follow artifact-reference consistency validation while the outer OS Profile Ownership Lock excludes writers. It must not instantiate `LoopPlaneHost`, call normal `assemble`, construct `SqliteCheckpointStore`/`FileCheckpointStore`/`ArtifactStore`, initialize schema, create any file/directory, or mutate pointer/proof/journals/profile state.
- The optional provider parameter exists for Host-owned composition and deterministic fault injection. Production Desktop composition uses the canonical Host-owned provider; arbitrary sidecar-defined validators are prohibited.
- Focused tests must prove zero Host instances, zero normal store constructors, zero filesystem creation/mutation, and unchanged source bytes before and after every success/failure. A caller-visible result is bounded and public-safe.
- All three facades use public-safe failure categories and do not return raw storage paths, SQLite errors, artifact content, credentials, or private configuration.

The implementation may place these providers in Host-owned modules and add storage-specific read-only adapters, but may not add snapshot or validation methods to the general checkpoint record contract if doing so would change unrelated backend obligations without a separate approved design.

## 10. Privacy and public-safety invariants

Outside the authorized conversation/history and referenced-artifact content surfaces, the following must never appear in renderer-visible status/IPC metadata, runtime-event wrapper metadata, Host/Web projections, audit, backup manifest metadata/entry names, protocol errors, logs, user documentation examples, or committed test snapshots:

- provider credentials/tokens/keys;
- raw private capability configuration, endpoints where private, or rule expressions;
- absolute/canonical workspace/archive paths or home/user directory fragments;
- rejected sensitive input echo;
- PIDs/process command lines;
- stderr, tracebacks, exception representations, or unbounded provider errors.

Authorized conversation/history payloads and eligible `gateway_tool_output` artifacts remain lossless and may themselves contain user-, model-, or tool-produced sensitive values or workspace excerpts. Exact normalized event forwarding is permitted only into the authorized conversation projection; event-class tests must prove those values do not cross into status, audit, diagnostic, error, log, or manifest metadata.

Trusted main-to-sidecar RPC may carry native-selected workspace/archive paths only for the exact operation. These values are ephemeral, never written to protocol diagnostics/logs, and are excluded from backup/profile/checkpoints/events.

## 11. Default preservation and tests required by this contract

Before implementation can be accepted, focused tests must prove:

- existing Host resume with no scope retains `Path.cwd()` semantics;
- resumed interactive context reuses existing principal/history/model/context and can submit/cancel/answer safely;
- supplied validated scope is applied only to the resumed Desktop interaction;
- failed enter/attach/callback/cancel/shutdown releases sink/reviewer/Host and Desktop leases;
- the canonical-root OS ownership lock is acquired before recovery/store/Host work; same-root and aliased-root second processes receive public-safe `busy` with zero Host/interaction lease, unsupported/remote/ambiguous locking fails closed, normal release follows teardown, and process crash permits only kernel-released later recovery;
- cross-principal session IDs are enumeration-safe;
- fresh bootstrap publishes/reopens the initial generation and canonical publication receipt with checkpoint/artifact `absent_uninitialized`, proves both payloads absent without opening/creating either store, leaves first initialization to normal Host/store owners, writes/rereads its receipt-bound proof before the exact pointer, completes a proof-without-pointer state only for a pristine receipt-valid profile, and constructs zero Host instances for unexpected payloads or every other pointer/proof/receipt mismatch;
- generation publication proves POSIX regular-file/bottom-up-directory/both-parent `fsync` plus same-filesystem rename under the physical-power-loss claim, and Windows regular-file `FlushFileBuffers`/supported-local-volume/write-through move/reopen under the process/application-crash claim; unsupported/error outcomes fail before pointer mutation and Windows parent-directory physical-power-loss durability is explicitly not claimed;
- proof post-effect/pre-acknowledgement ambiguity causes zero in-process rollback/cleanup/binding mutation and is adjudicated only by startup;
- a normal committed turn may mutate the active generation and restart validates current schema/SQLite/artifact consistency without comparing it to publication-time hashes;
- stale/missing/moved/replaced/link workspaces never silently run, and `relink_required` blocks lookup/reuse of an identical-ID pre-restore binding until explicit relink;
- renderer/workspace/audit/error projections contain no raw paths/secrets/private config;
- audit ordering is stable and derived without new checkpoint/event records;
- Host-owned portable snapshot/validation provides consistent SQLite and provenance-eligible artifact evidence without exposing live store internals or mutating staging during validation;
- backup/restore lease ownership spans the complete contract windows and rejects every competing session/interaction/Project/workspace/capability/profile/backup/restore writer before dispatch, while owning restore transitions and bounded teardown cannot begin unrelated durable work;
- authorized conversation/artifact sensitive markers remain confined to those content surfaces and do not cross into secondary status/audit/error/log/manifest metadata;
- Desktop's explicit SQLite selection and default-`None` snapshot provider do not change non-Desktop/default Host storage behavior.
