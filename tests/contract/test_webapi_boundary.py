"""Boundary and cross-cutting contract tests for the web/API host (011;
NFR-001-NFR-003, NFR-006, SC-003/006).

The layer is a thin transport over the public Host Application Interface: it
composes only ``loopplane.host`` + ``loopplane.events`` (plus the FastAPI/Starlette
transport), executes no tool, never re-emits the live event bus, keeps response
bodies metadata-only, and defaults to deny.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.webapi.models import (  # noqa: E402
    ErrorResponse,
    HistoryEntryView,
    RunResult,
    SessionSummaryView,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPI_DIR = REPO_ROOT / "src" / "loopplane" / "webapi"

ALLOWED_PREFIXES = (
    "loopplane.events",
    "loopplane.host",
    "loopplane.webapi",
)
# Runtime-internal / re-emit surfaces this layer must never reach.
PROHIBITED_TOKENS = (
    "RuntimeController",
    "ToolGateway",
    "Dispatcher",
    "run_loop",
    "EventEmitter",
    ".emit(",
    "loopplane.controller",
    "loopplane.gateway",
    "loopplane.dispatcher",
    "loopplane.loop",
)


def _modules() -> list[Path]:
    return sorted(WEBAPI_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_webapi_imports_only_host_and_event_surfaces() -> None:
    violations: list[str] = []
    for path in _modules():
        for node in ast.walk(_parsed(path)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith("loopplane") and not any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in ALLOWED_PREFIXES
                ):
                    violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_webapi_references_no_runtime_internal_or_bus() -> None:
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, "Runtime-internal / re-emit references:\n" + "\n".join(
        violations
    )


def test_webapi_response_models_are_metadata_only() -> None:
    # Response projections carry only ids / counts / public-safe reasons — never
    # a content block or tool I/O (FR-016, NFR-006, SC-003).
    assert set(HistoryEntryView.model_fields) == {"role", "block_count"}
    assert set(RunResult.model_fields) == {
        "session_id",
        "termination_reason",
        "turns_taken",
        "history",
        "consumer_failures",
    }
    assert set(SessionSummaryView.model_fields) == {"session_id", "label"}
    assert set(ErrorResponse.model_fields) == {"detail"}


def test_webapi_defaults_to_deny() -> None:
    # An app built with no authenticator denies a representative request.
    import tempfile

    from loopplane.webapi import create_app
    from tests.webapi_helpers import build_test_host, make_client, multi_text_model

    with tempfile.TemporaryDirectory() as tmp:
        host = build_test_host(Path(tmp), model=multi_text_model("a"), tools=())
        client = make_client(create_app(host))
        assert client.post("/v1/runs", json={"prompt": "x"}).status_code == 401
