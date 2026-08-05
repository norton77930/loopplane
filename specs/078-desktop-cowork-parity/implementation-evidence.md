# 078 Desktop Cowork Parity Implementation Evidence

This file records bounded evidence only. It is not approval authority: later gates must independently refetch and verify their required immutable review, commit, tree, and blob authorities.

## Stage A — PyInstaller build-lock materialization

<!-- STAGE-A-EVIDENCE START -->

- **External-human approval reference**: In the current interactive Claude Code session, the human user selected `批准 Stage A (Recommended)` in response to the explicit 078 Stage A gate prompt. The approved scope was limited to the three paths listed below and expressly excluded install, build, product/test source, workflow/manifest changes, commit, push, and PR creation.
- **Materialized at (UTC)**: `2026-07-31T16:55:38.579Z`
- **Approved direct input**: `pyinstaller==6.21.0`
- **Target interpreter**: Python `3.12`
- **Target platform**: `x86_64-pc-windows-msvc`
- **Resolver**: `uv 0.11.16 (135a36367 2026-05-21 x86_64-pc-windows-msvc)`
- **Compile constraints**: complete transitive resolution with `--generate-hashes --only-binary :all:`
- **Stage A write set**:
  - `apps/desktop/sidecar/pyinstaller-build.in`
  - `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`
  - `specs/078-desktop-cowork-parity/implementation-evidence.md`
- **Direct-input SHA-256**: `91aedc3e7790bedcabc79b3bd897ba9498252b290887d686ee9a393e9da26cb2`
- **Candidate PyInstaller lock SHA-256**: `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`
- **Resolved package count**: `7`
- **Resolved packages**: `altgraph`, `packaging`, `pefile`, `pyinstaller`, `pyinstaller-hooks-contrib`, `pywin32-ctypes`, `setuptools`
- **Structural validation**: PASS — the input is byte-exact, PyInstaller is pinned to `6.21.0`, the resolved package set is complete for this candidate lock, every package stanza carries SHA-256 hashes, and the generated-command header records Python 3.12, Windows x64, hash generation, and wheels-only resolution.
- **Runtime metadata check**: PASS — no `pyinstaller` reference occurs in `pyproject.toml` or `uv.lock`; the tool remains build-only.
- **Deterministic regeneration**: PASS — a second execution of the exact compile command produced the same lock SHA-256 before and after: `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`.
- **Excluded actions**: No dependency installation, product/test build, source/test/workflow/manifest/package-lock modification, commit, push, or PR was performed during Stage A. Pre-existing working-tree changes and `.superpowers/**` were not included or modified by Stage A.
- **Gate posture**: ADR 0015 remains `Proposed`. This candidate lock is not an accepted build input and authorizes no T003/T004 or product implementation. T002 still requires a distinct submitted external-human Stage-B bootstrap review and independent immutable GitHub authority verification.

Exact materialization command:

```powershell
uv pip compile apps/desktop/sidecar/pyinstaller-build.in `
  --output-file apps/desktop/sidecar/pyinstaller-build-windows-py312.txt `
  --python-version 3.12 `
  --python-platform x86_64-pc-windows-msvc `
  --generate-hashes `
  --only-binary :all:
```

<!-- STAGE-A-EVIDENCE END -->

## Stage B bootstrap (T002) — submitted review authority (comparison record only)

<!-- STAGE-B-BOOTSTRAP-EVIDENCE START -->

This block is a **comparison output only**. It is not locator authority and not final Stage-B acceptance. Later verifier modes must receive the immutable T002 review-ID/expected-commit pair as invocation inputs and rederive all values from GitHub API + content-addressed commit authority.

### Gate checks (refetched 2026-08-05)

| Check | Result |
|-------|--------|
| PR | `norton77930/loopplane` #3 (open) |
| PR author | `norton77930` |
| Review ID | `4864730949` |
| Review node ID | `PRR_kwDOS4xEH88AAAABIfXnRQ` |
| Review API URL | `https://github.com/norton77930/loopplane/pull/3#pullrequestreview-4864730949` |
| `state` | `APPROVED` |
| `submitted_at` | `2026-08-05T13:16:24Z` |
| Reviewer login | `norton777930` |
| `user.type` | `User` |
| `author_association` | `COLLABORATOR` |
| PR-author inequality | PASS (`norton777930` ≠ `norton77930`, case-insensitive) |
| Reviewed `commit_id` | `5319634a7e5c77b21ffa5355595fae18f9d82083` |
| PR head equality | PASS (equals PR #3 head at verification) |
| Reviewed tree SHA | `e98d150035560eac0b44cda16fda63e647f748cc` |
| Tree `truncated` | `false` (API recursive tree) |
| ADR 0015 status | **Proposed** (unchanged; bootstrap must not accept ADR) |
| Authorization | **T003 + T004 only** (no T006+ product work; no install/build; no freeze/package) |

### Recorded identities (non-authoritative locators for human comparison)

- **Stage B Bootstrap Approval API URL:** `https://github.com/norton77930/loopplane/pull/3#pullrequestreview-4864730949`
- **Stage B Bootstrap Approval ID:** `4864730949`
- **Stage B Bootstrap Approval Node ID:** `PRR_kwDOS4xEH88AAAABIfXnRQ`
- **Stage B Bootstrap Approval Submitted At:** `2026-08-05T13:16:24Z`
- **Stage B Bootstrap Approver Login:** `norton777930`
- **Stage B Bootstrap Reviewed Commit SHA:** `5319634a7e5c77b21ffa5355595fae18f9d82083`
- **Stage B Bootstrap Reviewed Tree SHA:** `e98d150035560eac0b44cda16fda63e647f748cc`
- **Stage B Bootstrap Review Bundle SHA-256:** `67f815901e64770453467786b6ccd3be25caedcf74b41527aeda2b6818a3961d`
- **Stage B Bootstrap Full-tree blob inventory SHA-256:** `291e88b754df9248a54d98a0ef8395dc6124ae9173490ef2192ef9d91453c24c` (local `git ls-tree -r` over reviewed commit; path/type/mode/blob lines)
- **Candidate PyInstaller lock SHA-256 (bound):** `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`

### Bootstrap bundle definition

Sorted relative paths + content SHA-256 (ordinal path order; line format `path␠␠sha256` + LF) over: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`, both checklists, all five contracts, complete Proposed ADR, `pyproject.toml`, `uv.lock`, `pyinstaller-build.in`, and candidate PyInstaller transitive lock (18 paths). Bundle SHA-256 is the UTF-8 SHA-256 of that manifest.

### Immutable invocation inputs for later modes (do not discover from this file)

- Owner: `norton77930`
- Repository: `loopplane`
- Pull request: `3`
- Expected approver (maintainer variable at T002 close-out): `norton777930`
- Optional C2 switch: `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` may remain `true` but was not required for this review (reviewer ≠ author)
- T002 bootstrap review ID: `4864730949`
- T002 expected commit SHA: `5319634a7e5c77b21ffa5355595fae18f9d82083`

### Explicit non-claims

- ADR 0015 is **not** Accepted.
- Root npm workspace/lock is **not** bound (T004/T005).
- Product source, verifier script, package freeze, and artifact smoke are **not** authorized.
- This evidence block cannot authorize itself or substitute for API refetch.

<!-- STAGE-B-BOOTSTRAP-EVIDENCE END -->

## T003 — delivery-gate RED observation

<!-- T003-RED-EVIDENCE START -->

- **When (local)**: after T002 bootstrap authorization
- **Artifacts**:
  - `tests/contract/test_desktop_delivery_gate.py`
  - `tests/helpers/desktop_stage_b_policy.py`
- **Command**: `uv run pytest tests/contract/test_desktop_delivery_gate.py -q`
- **Result**: **RED as required** — `32 failed, 8 passed`
  - 8 pure policy oracle tests pass (mode locators, C2 rule, tree-diff allowlist, extras)
  - 32 verifier entrypoint / `-SelfTest` cases fail because `scripts/verify-desktop-stage-b.ps1` is not yet implemented (T004)
- **Non-claims**: No product source, package manifests, workflow, or verifier implementation was added in T003.

<!-- T003-RED-EVIDENCE END -->

## T004 — verifier + final npm graph materialization

<!-- T004-EVIDENCE START -->

- **Verifier**: `scripts/verify-desktop-stage-b.ps1`
  - Modes: `bootstrap` | `final` | `delivery`
  - Credential seam: `LOOPPLANE_STAGE_B_GITHUB_TOKEN` only (no `GH_TOKEN`/`GITHUB_TOKEN` fallback)
  - `-SelfTest <case>` covers T003 contract cases without network
- **npm graph (pre-implementation final manifests)**:
  - root `package.json` (workspaces: web, desktop, cowork-presentation)
  - `packages/cowork-presentation/package.json`
  - updated `apps/web/package.json` / `apps/desktop/package.json` (workspace dep + final scripts/`main`/`files`)
  - sole root `package-lock.json`
  - removed app-local locks: `apps/web/package-lock.json`, `apps/desktop/package-lock.json`
- **Command**: `uv run pytest tests/contract/test_desktop_delivery_gate.py -q`
- **Result**: **GREEN** — `40 passed`
- **Non-claims**: No product presentation source scaffolding, no install/build of Desktop artifact, ADR remains Proposed, T006+ not authorized until T005.

<!-- T004-EVIDENCE END -->
