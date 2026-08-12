"""Packaged Desktop sidecar 的唯一 Python 進入點。"""

from bridge import main

# PyInstaller 以此 import 收集 packaged-smoke 使用的 scripted model module。
from loopplane.model import ScriptedModel as _ScriptedModel  # noqa: F401

if __name__ == "__main__":
    main()
