"""Phase-1 public-surface import guard (NFR-001) and the no-UI-dependency
constraint (FR-008).

The host layer composes Phase-1 only through its declared public modules, and
imports no web, transport, or UI framework — so it stays embeddable from a plain
process.
"""

from __future__ import annotations

import importlib
from pathlib import Path

PHASE1_SURFACE = [
    "loopplane.controller.controller",
    "loopplane.gateway",
    "loopplane.model",
    "loopplane.approval",
    "loopplane.checkpoint",
    "loopplane.artifacts",
    "loopplane.memory",
    "loopplane.skills",
    "loopplane.events",
    "loopplane.observability",
]

_FORBIDDEN = (
    "flask",
    "fastapi",
    "django",
    "starlette",
    "uvicorn",
    "aiohttp",
    "tornado",
    "tkinter",
    "PyQt",
    "PySide",
    "gradio",
    "streamlit",
)


def test_phase1_public_surface_imports() -> None:
    for module in PHASE1_SURFACE:
        importlib.import_module(module)
    importlib.import_module("loopplane.host")


def test_host_layer_imports_no_web_transport_or_ui_framework() -> None:
    host_dir = Path(__file__).resolve().parents[2] / "src" / "loopplane" / "host"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(host_dir.glob("*.py"))
    )
    for name in _FORBIDDEN:
        assert f"import {name}" not in source, name
        assert f"from {name}" not in source, name
