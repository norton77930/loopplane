# Contract: Portable Desktop Backup and Restore V1

**Status**: Proposed — implementation requires the 078 human gate.

**Format name**: `loopplane.desktop.backup`

**Format version**: `1.0`

## 1. User-facing privacy statement

Backup creation is blocked until the user sees and explicitly acknowledges all of the following:

1. The archive is **not application-encrypted** in V1.
2. LoopPlane-owned provider credentials/tokens, private capability configuration, private workspace path mappings, logs, raw internal errors, PIDs, caches, transient run state, unsent drafts, and any recursive/direct collection of arbitrary workspace contents are excluded.
3. Full session history and eligible referenced Gateway artifacts are preserved losslessly. User-, model-, or tool-produced content may contain credentials, secrets, personal data, absolute paths, copied workspace excerpts, or other sensitive values; those values remain in the archive. Unsent pane/composer drafts are excluded and are not recoverable.
4. The user must choose and protect the destination using operating-system controls.
5. Integrity hashes detect corruption; they do not provide encryption, authenticity, or protection from a malicious party who can rewrite the whole archive.

Acknowledgement is recorded in the manifest as a boolean and safe disclosure version, never as user text.

## 2. Backup preconditions

- The active profile generation opens successfully.
- No Desktop Interaction Lease, Profile Mutation Lease, or reserved Restore Transaction is active.
- Electron main validated the requesting renderer and obtained an explicit native save destination.
- The destination path is passed only over trusted main-to-sidecar RPC and is never returned, logged, checkpointed, added to events, or stored in the archive.
- The selected destination is not inside a workspace artifact/source tree unless the native chooser/user explicitly selected it; no implicit destination is used.
- If replacement of an existing file is allowed, the native chooser and application confirmation make that replacement explicit.

Failure of any precondition performs no profile or destination mutation.

## 3. Archive container

- Container: ZIP using Python standard-library `zipfile`.
- Allowed entry type: regular file only.
- Allowed compression: stored or DEFLATE only.
- No encryption flag, data-descriptor ambiguity outside supported stdlib behavior, symlink, hard link, reparse-point surrogate, device, FIFO, socket, executable restoration semantics, alternate data stream, or platform-special entry is accepted.
- `manifest.json` is required, stored at archive root, and parsed before any profile publication.
- Restore never calls `extractall()`; it streams each declared entry to a newly created staging file after path and metadata validation.

## 4. Manifest

`manifest.json` is UTF-8 canonical JSON with sorted keys, no duplicate keys, finite values only, maximum depth 32, and maximum size 8 MiB.

Example shape:

```json
{
  "format":"loopplane.desktop.backup",
  "version":{"major":1,"minor":0},
  "profile_schema_version":1,
  "created_at":"2026-07-30T00:00:00Z",
  "profile_id":"opaque-uuid",
  "principal_id":"opaque-uuid",
  "disclosure":{"version":1,"acknowledged":true},
  "totals":{"entries":3,"compressed_bytes":100,"uncompressed_bytes":200},
  "entries":[
    {
      "path":"profile/profile.json",
      "kind":"regular_file",
      "content_class":"profile",
      "size":100,
      "sha256":"<64-lowercase-hex>"
    }
  ]
}
```

Rules:

- Entries are sorted by Unicode code point of normalized POSIX path.
- Every non-manifest archive entry appears exactly once in `entries`; undeclared archive entries are rejected.
- Every declared entry exists exactly once in ZIP central directory and local header view.
- Manifest totals match observed archive metadata and streamed bytes.
- Unsupported major fails closed. Minor compatibility is accepted only when all entries/classes/fields are recognized and optional-field rules are documented; V1.0 otherwise rejects unknown required structures.

## 5. Path safety

Every declared and actual archive name must:

- be a relative POSIX path using `/`;
- be valid normalized Unicode and UTF-8;
- contain no empty, `.` or `..` segment;
- contain no leading `/`, backslash, drive prefix, UNC prefix, colon-based alternate stream, NUL, control character, or terminal dot/space ambiguity;
- remain under the staging root after pure path resolution;
- be unique under exact comparison, Unicode normalization comparison, and platform case-fold comparison;
- be no longer than 1024 UTF-8 bytes in the archive and must map to a staging path supported by the current platform;
- match one exact content-class path allowlist.

Unsafe names are not echoed to renderer-visible errors.

## 6. Safety limits

V1 default limits:

| Limit | Value |
|---|---:|
| Archive file size | 4 GiB |
| Total uncompressed data | 8 GiB |
| Single entry uncompressed size | 2 GiB |
| Declared/actual non-manifest entries | 10,000 |
| Manifest size | 8 MiB |
| Path bytes | 1,024 |
| Aggregate expansion ratio | 200:1 |
| Validation/staging restore tokens | 1 per profile |
| Restore token lifetime | 15 minutes |

The validator checks central-directory declarations before staging and enforces actual streamed bytes independently. Exceeding any limit rejects safely. Limits are reported in `backup.describe` and may change only through a compatible versioned contract/human gate.

## 7. Inclusion allowlist

### Included

1. **Portable profile identity and safe preferences**
   - `profile/profile.json`
   - fixed `profile_id` and `principal_id`;
   - Desktop Projects, session membership, and optional opaque workspace association;
   - locale/theme/pane/sidebar safe preferences with unsent drafts removed;
   - opaque Workspace References and labels, forced to `relink_required` in exported/restored form.

2. **Existing session durability**
   - a consistent SQLite checkpoint snapshot under `sessions/checkpoints.sqlite3`, produced only by the additive Host-owned `export_portable_snapshot(destination)` facade;
   - all principal-owned sessions represented by that snapshot unless a future contract adds explicit subset export;
   - the sidecar never reads/copies the live SQLite path or connection directly.

3. **Referenced LoopPlane artifacts**
   - only V1 provenance-eligible `gateway_tool_output` files produced by the existing Gateway `ArtifactStore`, referenced by exported checkpoint data, and copied into the immutable Host-owned snapshot;
   - stored under deterministic opaque session/artifact paths with safe metadata (`session_id`, reference, call ID, media kind, size, digest, content origin);
   - source files must be regular, active-generation-rooted, no-follow/reparse-safe, metadata-consistent, and identity/size-stable before/after streaming;
   - full artifact bytes are retained and may contain copied workspace excerpts, paths, credentials, or other sensitive tool output covered by the disclosure;
   - no direct/recursive workspace or upload-store traversal occurs; missing, linked, replaced, unreferenced, or inconsistent artifacts cause backup failure rather than a silently incomplete success.

4. **Audit**
   - preferably re-derived from restored checkpoints;
   - a separate audit file is included only if the accepted implementation demonstrates that metadata cannot be re-derived and the file obeys the Turn Audit exclusion contract.

### Excluded

- provider API keys, OAuth tokens, bearer tokens, private keys, passwords, or credential-store exports;
- capability store/private MCP endpoints, private context source configuration, schedules, model/provider secrets, or other private configuration;
- device-private Workspace Bindings and all canonical/absolute paths;
- workspace/repository arbitrary files and directories;
- logs, raw internal/provider errors, tracebacks, stderr, diagnostic dumps;
- renderer caches, unsent pane/composer drafts, browser storage, temporary downloads/uploads not represented as eligible durable Gateway artifacts;
- PIDs, command lines, process/session sockets, locks, leases, subscriptions, pending RPC requests, approval/question waits, active-run state;
- staging directories, old generations, backup destinations/sources, or unrelated/orphan artifacts;
- `.superpowers/**` and other development/QA local records.

## 8. Backup creation algorithm and atomicity

1. Acquire the Profile Mutation Lease and require no active interaction. From this point through archive finalization, the dispatcher rejects `busy` before Host/profile dispatch for every competing active-generation or generation-external writer: session create/rename/star/fork/delete, interactive open/submit/answer, Project/workspace mutation (including persisted `workspace.revalidate`), capability action, backup, or restore. Only bounded shutdown/cancel/release teardown may proceed and it cannot start new durable work.
2. Re-read disclosure acknowledgement and destination preconditions.
3. Create a temporary archive beside the final destination with restrictive default permissions available to the process.
4. Invoke the additive Host-owned `export_portable_snapshot(empty_directory)` facade. It creates the consistent SQLite backup and provenance-checked referenced-artifact copies without exposing live store paths.
5. Enumerate allowlisted Desktop profile/project/safe-preference inputs plus the completed Host snapshot; never recursively archive the profile root, workspace, upload store, or live ArtifactStore.
6. Stream immutable snapshot/profile entries, calculate SHA-256 and sizes, and build the canonical manifest.
7. Write `manifest.json`, close/finalize ZIP, reopen and validate central metadata and manifest hashes against the just-created archive.
8. Flush file data; use `fsync` for file and containing directory where the platform supports it.
9. Publish with same-directory `os.replace` to the explicitly selected destination.
10. Release mutation lease and return only safe summary (format, counts, sizes, completion), not destination path.

Failure before step 9 removes/quarantines the temporary file and leaves an existing destination unchanged. Failure at/after publication is reported honestly; no profile data changes.

## 9. Restore validation

`restore.validate` is a side-effecting, mutation-idempotent staging operation. It requires native file selection and atomically reserves the Profile Mutation Lease after proving no active interaction/profile mutation/restore reservation. That reservation remains live until commit, cancel, expiry, connection shutdown, or sidecar restart cleanup. It:

1. opens the archive without extracting;
2. validates archive size, container flags, `manifest.json`, format/version/profile schema, disclosure record, entry counts/types/compression, path safety/collisions, central/local metadata consistency, and declared limits;
3. creates a same-volume staging generation outside the active generation;
4. streams each declared regular file to a newly created target using no-follow/exclusive creation semantics available on the platform;
5. enforces actual byte/ratio limits and SHA-256 while streaming;
6. validates `profile.json`, fixed identity fields, SQLite integrity/schema/application queries, principal ownership, artifact references/hashes, and all Desktop safe-state schemas;
7. rewrites Workspace Reference availability to `relink_required` and creates no device-private binding;
8. invokes the additive Host-owned `validate_portable_snapshot(staged_snapshot)` facade, which uses dedicated read-only SQLite URI/query and artifact-consistency validation without normal Host assembly, directory creation, or schema initialization;
9. returns a short-lived opaque `restore_token` plus a public-safe preview containing format/version, creation time, project/session/artifact counts, draft-exclusion notice, and relink requirement.

Validation returns no profile/principal/path/private-config data to renderer. `restore.validate` does not replace the active generation, but its staging/reservation is a profile mutation: a duplicate mutation ID returns the same terminal validation result/token. Until the reservation ends, the dispatcher rejects `busy` before Host/profile dispatch for every competing session create/rename/star/fork/delete, interactive open/submit/answer, Project/workspace mutation (including persisted `workspace.revalidate`), capability action, backup, or restore; only the owning `restore.commit`/`restore.cancel` and bounded shutdown/cancel/release teardown may continue, and teardown cannot start new durable work. Expiry/cancel/shutdown deletes or quarantines staging and releases the reservation.

## 10. Restore commit and rollback

`restore.commit` requires:

- the exact live restore token;
- explicit renderer confirmation through operation-specific IPC;
- same selected archive identity/content hash as validation (revalidated to prevent time-of-check/time-of-use replacement);
- no Desktop Interaction Lease;
- the same still-live exclusive Restore Transaction/Profile Mutation Lease reservation created by validation;
- supported current and source format/profile versions.

### Durable generation publication primitive

No pointer or Active Generation Proof may reference a Profile Generation until one fail-closed, platform-scoped generation-publication primitive has completed. For both initial-profile bootstrap and restore candidates, the primitive MUST:

1. require staging and `generations/` to be on the same supported local volume, reject links/reparse ambiguity, close all writers, and recursively enumerate the exact expected regular-file/directory inventory;
2. flush every present regular file (including SQLite and artifacts when initialized) after its final bytes using the platform's documented regular-file durability call;
3. publish the unique staging directory to the non-existing final `generations/<generation-id>` entry using the platform protocol below;
4. reopen the final generation by no-follow handles and validate its publication-time inventory, sizes/hashes, and profile schema before any pointer write. Restore/non-pristine generations additionally validate SQLite integrity/ownership and artifact consistency. A fresh zero-session bootstrap instead requires the receipt-declared `checkpoint_state=absent_uninitialized` and `artifact_state=absent_uninitialized`, proves both stores/payloads are absent without opening or creating them, and leaves first creation to normal Host/checkpoint/artifact ownership after Host construction; and
5. construct a canonical immutable **Generation Publication Receipt** containing the receipt version, generation ID, platform, accepted durability scope, publication sequence/nonce, declared checkpoint/artifact initialization state, and digest of the publication-time validation result. The receipt object/digest is embedded in the candidate pointer, both journal slots, and Active Generation Proof; it is internal recovery metadata and never renderer-visible.

The platform protocols and guarantees are deliberately different:

- **POSIX local filesystems**: flush/file-`fsync` every regular file, `fsync` generation directories bottom-up, `os.replace` the staging directory on the same filesystem, then `fsync` both the former staging parent and destination `generations/` parent. This is the 078 physical-power-loss durability claim for generation publication and is tested only on POSIX filesystems where those calls are supported.
- **Windows required artifact**: accept only a documented supported local filesystem set (initially local NTFS/ReFS; remote/network/removable or unrecognized volumes fail closed), call regular-file `FlushFileBuffers`, publish on the same volume with `MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` or an equivalently documented write-through replace, then reopen the final path and repeat bounded schema/SQLite/artifact consistency validation. This contract claims **process/application-crash consistency**, not sudden physical-power-loss persistence of both parent-directory metadata entries. The design does not treat an undocumented directory-handle `FlushFileBuffers` call as a proof of parent metadata durability. Any API failure, unsupported volume/filesystem, rename ambiguity, reopen failure, or validation failure returns public-safe `durability_unsupported`/`publication_failed` before pointer publication. Stage B must explicitly accept this Windows limitation.

A Profile Generation is quiescent during publication but becomes mutable after its Host is opened: checkpoints, artifacts, and safe profile state continue to change. The Generation Publication Receipt proves the immutable publication event and pointer/proof lineage; it is **not** a permanent hash of current generation contents. Startup validates the canonical receipt/checksum and its generation/pointer/proof binding, then validates the current mutable profile schema, SQLite integrity/ownership, and artifact consistency through current store rules. It never requires current mutable files to equal publication-time inventory hashes.

### Recovery records and durable-write primitive

The profile root uses four small recovery files outside every generation:

- `active-generation.json`: the current generation pointer;
- `active-generation-proof.json`: the independently durable proof for the only pointer that may be opened normally;
- `restore-journal-a.json` and `restore-journal-b.json`: redundant copy-on-write journal slots.

Every normal active pointer, including the initial profile generation before first Host construction, has one matching active-generation proof. Each pointer, proof, and journal record is bounded to 64 KiB canonical UTF-8 JSON, maximum depth 8 and 32 object keys; duplicate keys, unknown required fields, invalid base64/digests, or oversize records are invalid recovery evidence. The proof is canonical JSON containing an exact supported proof version, monotonic proof sequence, `proof_kind` (`bootstrap` or `restore`), optional `restore_id`, active generation ID, durable-generation receipt/digest, exact active-pointer bytes/base64 plus SHA-256, verified timestamp for diagnostics only, and a SHA-256 record checksum over the canonical object excluding the checksum field. A restore proof is written only after candidate readiness, old-Host close, and atomic runtime-owner installation have succeeded. The proof—not a journal filename's presence or timestamp—is the positive authority that permits startup to keep a candidate pointer.

Fresh-profile bootstrap is also proof-first and completes before the first Host construction or dispatch. It runs only when no committed pointer/proof pair or restore journal exists: publish the initial generation through the durable generation primitive with zero sessions and receipt-declared `checkpoint_state=absent_uninitialized`/`artifact_state=absent_uninitialized`, prove the SQLite file and artifact payload are absent without importing/opening/creating either private store, construct the exact pointer bytes and a checksummed `proof_kind="bootstrap"` proof bound to that receipt, durably write/reread the proof, then durably write/reread the exact pointer. Only after the Host is constructed may existing checkpoint/artifact owners create their stores on first durable use. A crash before proof durability leaves no committed profile and startup quarantines/retries bootstrap; a crash after proof but before pointer durability may complete only those exact pointer bytes from the valid bootstrap proof after revalidating the same pristine absent-uninitialized state and durable generation receipt. A pointer without its matching bootstrap proof, a bootstrap proof naming an invalid generation, unexpected pre-Host SQLite/artifact data, or any journal/identity conflict fails locked with zero Host. Only a reread-valid pointer/proof/generation triple permits construction of the initial `DesktopRuntimeOwner` Host.

Each journal slot is independently complete, canonical, checksummed JSON and contains: exact journal version, slot ID, monotonic journal sequence, restore/archive IDs, state (`prepared`, `published`, or `verified`), previous/candidate generation IDs, exact previous-pointer bytes/digest, exact previous-proof bytes/digest, exact candidate-pointer bytes/digest, optional candidate-proof digest after verification, and diagnostic timestamp. Sequence is compared only among checksum-valid records for the same restore lineage and exact recovery preimages. The initial two `prepared` records may share one sequence only when state and all recovery fields match and only slot/checksum differ; any other equal-sequence disagreement, conflicting lineage, or inconsistent preimage fails locked rather than being ordered by time.

Every recovery-file mutation uses one required platform durable-replace primitive: create a unique same-directory temporary regular file, write the complete bytes, flush the regular file, atomically replace the target, then reread and validate checksum/content. POSIX additionally `fsync`s the parent directory after each replace/unlink and carries the physical-power-loss claim. Windows uses documented regular-file `FlushFileBuffers`, same-volume `MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` or an equivalently documented write-through replace, and post-replace reopen; it carries only the process/application-crash guarantee above and does not claim undocumented parent-directory physical-power-loss durability. Unsupported/error outcomes fail before advancing state. After the initial equal-sequence `prepared` pair, the first transition replaces slot A and preserves slot B; later transitions replace the lower-sequence slot. Every journal state change therefore leaves the other checksum-valid full recovery preimage untouched until a matching active-generation proof is independently durable. Cleanup is one file at a time after authoritative proof or rollback, with POSIX parent-directory `fsync` and Windows write-through/reopen checks under the same platform-scoped guarantees.

### Commit steps

1. Revalidate token, archive identity/hash, staged files, reservation, and free-space/publication preconditions.
2. Assign a new opaque generation ID and publish staging through the platform-scoped generation-publication primitive. Retain the canonical Generation Publication Receipt object/digest; any unsupported/error result stops before pointer mutation.
3. Read and validate that the exact existing `active-generation.json` and `active-generation-proof.json` match each other. Capture both exact byte strings/digests, construct the exact canonical candidate-pointer bytes/digest embedding the candidate publication-receipt digest, and refuse publication if the previous committed state is not independently proven.
4. Write a complete checksummed `prepared` record to **both** journal slots using the platform durable-write primitive, with independently validated slot IDs, the same restore lineage/recovery preimages, and the canonical candidate receipt object/digest. Pointer publication is forbidden until both slots reread validly under the applicable platform guarantee.
5. Replace `active-generation.json` with the exact candidate pointer through the platform durable-write primitive. Then copy-on-write the older journal slot to a higher-sequence `published` record, leaving the other valid `prepared` slot and its full recovery preimage intact.
6. Through the sidecar's sole `DesktopRuntimeOwner`, compose and readiness-check a fresh `LoopPlaneHost` rooted at the candidate generation while the old Host remains quiescent and receives no new dispatch. Readiness covers restored profile/Project/session/checkpoint/eligible-artifact stores through normal composition.
7. After candidate readiness succeeds, close the old Host and atomically install the candidate Host in the runtime owner. Only then replace `active-generation-proof.json` through the platform durable-write primitive with a checksummed proof matching the exact candidate-pointer bytes, generation, canonical publication receipt/digest, and restore ID; reread it and require it to match the still-current pointer and the current schema/SQLite/artifact consistency checks.
8. A reread-valid matching proof is the restore commit authority: after startup or the current process establishes that authority, recovery never rolls the candidate back merely because the later journal transition or cleanup is interrupted. Copy-on-write the older journal slot to a higher-sequence `verified` record referring to the proof digest, finalize state `committed`, and release the reservation; any failure here becomes resumable cleanup while dispatch remains on the candidate Host. Journal slots may then be removed one at a time only after the pointer/proof pair is reread successfully; a crash during cleanup is recoverable from the independent proof. Every subsequent request uses the candidate Host only.
9. Rollback is permitted only when proof publication is definitively known not to have taken effect. If pointer publication, candidate construction/readiness, old-Host close, or owner swap fails before proof publication starts—or proof replacement definitively fails without changing the target—close the candidate and use a checksum-valid, lineage-consistent journal slot to restore the exact previous proof/pointer bytes and a usable previous-generation Host. **If proof replace/flush/reopen may have taken effect but acknowledgement is missing or uncertain, perform no rollback, cleanup, binding deletion, or further pointer/proof/journal mutation.** Stop dispatch, retain both journals, enter a public-safe restart-required fail-locked state, and let startup reread the pointer/proof/receipt: a matching proof commits the candidate; otherwise a valid journal restores the previous pair. If no valid full preimage exists or a matching previous Host cannot be restored, remain fail locked and construct no Host rather than guessing.
10. Retain the previous generation until verified success and a later explicit safe cleanup point. Every restored Workspace Reference is written as `relink_required`, and that state is checked **before** any device-private binding lookup. An old binding with the same `profile_id`/`workspace_id` is ignored and cannot authorize candidate readiness or interaction. Previous bindings may remain quarantinable recovery data until candidate proof is authoritative so rollback can still serve the previous generation; only afterward may stale candidate-incompatible bindings be quarantined/deleted one at a time. Explicit successful relink creates the new current-device binding.

Before pointer replacement, any failure leaves the old active pointer/proof pair and generation byte-identical. After pointer replacement, a candidate may remain active only when the current pointer has its independently durable matching proof. Otherwise a valid redundant journal preimage deterministically restores the exact previous proof/pointer pair; absent or ambiguous recovery evidence fails locked before Host construction. Restore never merges into a live profile in place.

## 11. Identity and conflict semantics

- Restore replaces the active portable profile with the backup's `profile_id` and `principal_id`; it does not merge principals.
- This replacement is authorized only by explicit local file selection, validation preview, and confirmation while idle.
- Device-private bindings are not carried across even when the destination machine is the same.
- Existing destination generations remain rollback data, not automatically merged session data.
- Import/merge, selective conflict resolution, and cross-user backup sharing are outside V1.

## 12. Cancellation, interruption, and startup recovery

- Cancelling before publication deletes/quarantines staging and leaves the active pointer/proof pair unchanged.
- Process/app crash during validation or staging invalidates the process-local token; startup proves any staging is not active/referenced, removes or quarantines it, and releases the stale reservation.
- Crash after generation publication but before pointer replacement leaves an inactive generation; startup does not activate it automatically.
- Before any normal Host construction, startup reads `active-generation.json`, `active-generation-proof.json`, and both journal slots independently with strict canonical/schema/checksum validation. It validates the embedded canonical Generation Publication Receipt and its pointer/proof/generation binding, then invokes only the public non-instance `loopplane.host.validate_active_generation(...)` facade for the named **current mutable generation**. A receipt-declared zero-session pristine bootstrap supplies `absent_uninitialized` expectations and receives no-follow absence checks only; every initialized generation supplies proof/receipt-derived profile/principal/state expectations and receives dedicated read-only profile-schema, SQLite integrity/ownership, and artifact-consistency checks. The facade constructs zero `LoopPlaneHost` instances and zero normal checkpoint/artifact stores, creates/mutates no files, and returns no storage handle/path. Startup does not compare current checkpoints/artifacts/profile bytes to publication-time hashes and does not delete unreadable evidence until recovery has completed or the profile is explicitly quarantined.
- On a pristine bootstrap only, a valid `proof_kind="bootstrap"` proof with no pointer may recreate exactly the pointer bytes embedded by that proof after receipt binding plus current absent-uninitialized validation; any unexpected store data or other missing/mismatched bootstrap component fails locked or restarts pre-commit bootstrap without constructing a Host.
- A current pointer with a matching valid active-generation proof and matching canonical publication receipt is the only normal-open condition. If the proof correlates to the candidate/restore in any surviving journal slot, startup treats the commit as verified, completes safe journal and stale-binding cleanup, and opens exactly the proved generation; an older `prepared`/`published` slot cannot override the independent proof.
- If the pointer still matches the previous proof and a valid `prepared` journal exists, startup leaves/restores the exact previous pair, keeps the candidate inactive, and cleans the abandoned restore.
- If the current pointer lacks a matching proof but at least one checksum-valid, lineage-consistent journal slot contains the complete previous proof/pointer preimage, startup restores those exact bytes through the platform durable-write primitive before constructing one previous-generation Host. This startup reread is also the **only** adjudicator after an in-process proof-write effect/acknowledgement ambiguity; the prior process must not have attempted rollback or cleanup. One torn, truncated, corrupt, or missing slot is tolerated from the other valid slot at every state transition.
- If both journal slots are unavailable/invalid/ambiguous before a matching candidate proof is authoritative, or the pointer/proof pair cannot be matched to a valid recovery lineage, startup fails locked with no Host and a bounded public-safe recovery state. It never treats an unproved candidate as active or guesses from generation presence, publication-time inventory hashes, sequence across conflicting restore IDs, or modification time.
- Journal cleanup is legal only after either exact rollback has produced a matching previous pointer/proof pair or a matching candidate proof is independently durable. Slots are removed one at a time with directory durability, so interruption during cleanup leaves either a usable slot or the authoritative proof.
- After rollback/verified completion, startup cleans or retains candidate/previous generations only according to explicit safe cleanup; it never guesses from modification time.
- No recovery path guesses a workspace path or silently selects a different principal/generation.

## 13. Public-safe results and errors

Renderer-visible success may include:

- archive format/version;
- creation timestamp;
- entry/project/session/artifact counts and unsent-draft exclusion notice;
- compressed/uncompressed sizes;
- disclosure version acknowledged;
- restore compatibility and `relink_required` notice.

Backup/restore may classify an internal bounded cause as `unsafe_archive`, `incompatible_backup`, `integrity_failed`, `limit_exceeded`, `profile_busy`, `insufficient_space`, `durability_unsupported`, `publication_failed`, `rolled_back`, or `cancelled`, but these names are never RPC `error.data.category` values. The single normative cause-to-wire mapping is the table in the Desktop IPC contract: each cause selects one existing RPC code/category/retryable/recovery row plus one fixed allowlisted `messageKey`; the explicit unknown-cause row maps to `-32603 internal_failure`, `retryable=true`, `restart_runtime`, and exactly `desktop.error.internal_failure`. It never includes archive entry names when unsafe, source/destination paths, raw SQLite errors, exception strings, hashes of secrets, principal ID, or private configuration.

## 14. Required evidence

Acceptance requires automated evidence for:

- complete valid round trip of Desktop Projects, sessions, safe preferences with drafts absent, principal, audit derivation, and provenance-eligible referenced artifacts;
- explicit disclosure acknowledgement and no implicit destination;
- zero exported LoopPlane-owned credentials/private config/workspace bindings/arbitrary workspace files/logs/PIDs/transient state;
- user-, model-, and tool-produced sensitive conversation/eligible-artifact content retained losslessly, unsent drafts excluded, and disclosure documented honestly;
- malformed JSON/ZIP, unsupported version/compression, undeclared/duplicate/case-fold/normalization-collision entries, traversal, absolute/drive/UNC/backslash/ADS names, symlink/special entries, oversized/zip-bomb/short-read/hash mismatch;
- Host-owned SQLite snapshot consistency, dedicated read-only staged validation, and provenance/no-follow/identity-checked artifact completeness without sidecar live-store reach-through;
- backup lease acquisition before Host snapshot/profile serialization through archive finalization and restore reservation before staging through commit/cancel/expiry/shutdown cleanup, each raced against session create/rename/star/fork/delete, interactive open/submit/answer, Project/workspace/capability/profile mutation (explicitly including `workspace.revalidate` persistence), competing backup/restore, owning restore transitions, and bounded teardown; competing durable work must fail before Host/profile dispatch and teardown must start none;
- fresh-profile bootstrap interruption before/after initial generation publication, bootstrap-proof replacement, pointer replacement, and every reread, proving explicit checkpoint/artifact `absent_uninitialized` state, public non-instance `loopplane.host.validate_active_generation(...)` use, no sidecar or facade store creation, first-normal-Host ownership, unexpected-payload fail-lock, and zero Host before a valid pointer/proof/publication-receipt triple;
- interruption at each validation/publication step;
- active profile byte-identical before pointer publication failures under the platform guarantee;
- POSIX fault injection for every candidate/initial regular-file `fsync`, bottom-up directory `fsync`, same-filesystem rename, both parent-directory `fsync`s, reopen/publication-time inventory/schema/SQLite/artifact validation, plus documented physical-power-loss evidence only on exercised supported filesystems;
- Windows fault injection for every regular-file `FlushFileBuffers`, supported-local-volume check, same-volume write-through move/replace, post-move reopen, current schema/SQLite/artifact validation, unsupported/remote volume, API failure, and process termination boundary; evidence must state that sudden physical-power-loss persistence of both parent-directory entries is not claimed;
- fault injection after each journal temp write/file flush/replace/platform post-replace check, after pointer publication, after candidate Host construction/readiness/old-Host close/runtime-owner swap, before/after proof publication, **after proof write/flush effect but before successful reread/acknowledgement**, at each journal state transition, and between each cleanup unlink; the ambiguous proof-effect case must preserve both journals, perform zero recovery-file/binding mutation, fail locked, and let startup decide proof-versus-rollback;
- each journal slot independently torn, truncated, corrupt, or missing at every post-pointer boundary while the other valid full-preimage slot still proves exact rollback; conflicting/equal-sequence records fail locked;
- both slots unavailable/invalid before a matching candidate proof produce a bounded fail-locked no-Host state, never candidate activation, while journal loss after durable matching proof still permits candidate startup and cleanup;
- active-proof temp/replace corruption or an absent/mismatched proof is contained: a valid journal rolls back exactly, and no valid journal fails locked before Host construction; initialized and pristine startup validation fault injection proves the public active-generation facade performs zero Host/store construction and zero filesystem creation/mutation on every outcome;
- deterministic exact previous proof/pointer rollback and previous-Host recomposition unless the candidate pointer has an independently durable matching proof written after runtime-owner swap;
- post-commit reads and writes use only the candidate-generation Host, while rollback uses only a usable previous-generation Host and never stale/candidate mixed stores;
- after a normal committed turn mutates checkpoints/artifacts/profile state, restart still accepts the immutable publication receipt lineage while independently validating the current mutable generation; no publication-time hash comparison falsely locks the profile;
- restored Desktop Projects/session membership remain intact, while every Workspace Reference requires explicit relink; `relink_required` is checked before binding lookup, and an old device-private binding with identical profile/workspace IDs is ignored until explicit relink, cannot authorize candidate readiness/interaction, and is cleaned only after proof authority;
- every internal backup/restore cause selects the exact Desktop IPC table row for RPC code/category, retryability, required-or-absent recovery, and fixed `messageKey`; internal cause labels never become outward categories, and the unknown fallback is exactly `-32603 internal_failure`/`true`/`restart_runtime`/`desktop.error.internal_failure`;
- isolated profile restore without development checkout access.
