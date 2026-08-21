"""Packaged Desktop sidecar 的唯一 Python 進入點。"""

from typing import TYPE_CHECKING

from bridge import main

if TYPE_CHECKING:
    # 保留 packaged-smoke 的明確型別契約，不在協定握手前載入模型模組。
    from loopplane.model import ScriptedModel as _ScriptedModel  # noqa: F401

if __name__ == "__main__":
    main()
