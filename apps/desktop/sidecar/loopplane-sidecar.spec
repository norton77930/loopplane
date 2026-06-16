# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec (unit 024): freeze the desktop sidecar (bridge.py + loopplane) into a
# standalone `loopplane-sidecar` executable, so the packaged desktop app needs no system
# Python. Build (reserved manual / CI):
#   cd apps/desktop && pyinstaller sidecar/loopplane-sidecar.spec \
#       --distpath sidecar/dist --workpath sidecar/build
# This is a `.spec` (not a `.py`), so ruff / mypy / pytest ignore it. `collect_submodules`
# bundles loopplane's lazily/dynamically imported subpackages that bridge.py does not
# import statically.

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("loopplane")

a = Analysis(
    ["bridge.py"],
    pathex=[],
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
    a.binaries,
    a.datas,
    [],
    name="loopplane-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
