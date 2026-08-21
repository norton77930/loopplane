# -*- mode: python ; coding: utf-8 -*-
"""只從 verifier-materialized reviewed source 凍結 Desktop sidecar。"""

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

sidecar_root = Path(SPECPATH).resolve()
build_root = sidecar_root.parents[2]
loopplane_src = build_root / "src"
entrypoint = sidecar_root / "__main__.py"

for required in (loopplane_src / "loopplane", entrypoint):
    if not required.exists():
        raise SystemExit("sealed sidecar source is incomplete")

sys.path.insert(0, str(loopplane_src))
sys.path.insert(0, str(sidecar_root))
# Desktop can dynamically select built-in model adapters via LOOPPLANE_MODEL.
# All other runtime modules are collected from the static import graph; collecting
# every loopplane submodule bloats the frozen startup beyond the 5-second handshake.
hiddenimports = collect_submodules("loopplane.adapters")

a = Analysis(
    [str(entrypoint)],
    pathex=[str(loopplane_src), str(sidecar_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="loopplane-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="loopplane-sidecar",
)
