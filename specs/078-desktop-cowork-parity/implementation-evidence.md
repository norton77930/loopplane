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
