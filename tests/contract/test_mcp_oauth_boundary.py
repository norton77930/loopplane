"""Boundary contract tests for interactive MCP authorization (unit 084; ADR 0019 D3).

Two of this unit's requirements are negatives, and a negative is exactly what an
incidental test proves badly: a run that happens not to open a browser proves only
that this run did not. Both are therefore enforced constructively, by walking the
AST of every module under ``src/loopplane``:

* **Nothing binds a listening socket or opens a browser.** The host does both,
  because a runtime is frequently a headless server process (spec FR-001, FR-005;
  contract C1.3).
* **Nothing writes authorization material to disk.** The only store the package
  ships is in-memory; durability is the host's decision (spec FR-007; contract C4.2).

The matchers below are deliberately narrow. An earlier draft flagged any call named
``bind`` and caught ``sink.bind(on_event)`` in ``host/host.py`` — an event-bus
binding, not a socket. A guard that cries wolf gets an exemption written for it, and
the exemption is what actually costs you the property later.

Each guard has a companion test that plants a violation into a synthetic module and
asserts the scanner rejects it. Without that, a guard whose matcher is subtly wrong
passes forever by finding nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "loopplane"
OAUTH_MODULE = SRC_ROOT / "adapters" / "mcp" / "oauth.py"

# Importing any of these is, by itself, the capability we are refusing to have.
# Measured against the tree at unit 084: none of them appears anywhere in
# ``src/loopplane``, so this guard starts from a real zero rather than an aspiration.
LISTENER_AND_BROWSER_IMPORTS = frozenset(
    {"socket", "socketserver", "http.server", "webbrowser"}
)

# Calls that create a listener or open a browser without necessarily importing one of
# the modules above (``anyio.create_tcp_listener``, ``asyncio.start_server``, ...).
LISTENER_AND_BROWSER_CALLS = frozenset(
    {
        "create_server",
        "create_tcp_listener",
        "create_unix_listener",
        "start_server",
        "serve_forever",
        "HTTPServer",
        "ThreadingHTTPServer",
        "open_new",
        "open_new_tab",
        "startfile",
    }
)

# Process spawning is a different question. Unit 052's sandboxed ``run_command`` is
# built on it and is entitled to it; the point of this guard is that *authorization*
# never launches anything, so the one legitimate owner is named rather than hidden.
PROCESS_IMPORTS = frozenset({"subprocess", "multiprocessing"})
PROCESS_CALLS = frozenset({"Popen", "fork", "spawnl", "spawnv", "execv"})
PROCESS_ALLOWED = frozenset({"tools/execution.py"})

# Filesystem-writing calls, checked only inside the OAuth module: the wider runtime
# legitimately writes checkpoints, artifacts, and ledgers.
WRITE_CALLS = frozenset(
    {"open", "write_text", "write_bytes", "mkdir", "touch", "rename", "replace"}
)
PERSISTENCE_IMPORTS = frozenset({"shelve", "sqlite3", "pickle", "dbm"})


def _modules() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _scan(tree: ast.AST, *, calls: frozenset[str], imports: frozenset[str]) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names if a.name in imports}
        elif isinstance(node, ast.ImportFrom) and node.module in imports:
            found.add(node.module)
        elif isinstance(node, ast.Call):
            name = _called_name(node)
            if name in calls:
                found.add(f"call:{name}")
    return found


def test_runtime_never_listens_or_opens_a_browser() -> None:
    """C1.3 — the host presents the URL and receives the redirect, never the runtime."""
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hits = _scan(
            tree,
            calls=LISTENER_AND_BROWSER_CALLS,
            imports=LISTENER_AND_BROWSER_IMPORTS,
        )
        if hits:
            offenders[path.relative_to(SRC_ROOT).as_posix()] = hits
    assert offenders == {}, f"runtime must not listen or open a browser: {offenders}"


def test_only_the_sandbox_executor_spawns_processes() -> None:
    """Authorization launches nothing; unit 052's run_command legitimately does."""
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        rel = path.relative_to(SRC_ROOT).as_posix()
        if rel in PROCESS_ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hits = _scan(tree, calls=PROCESS_CALLS, imports=PROCESS_IMPORTS)
        if hits:
            offenders[rel] = hits
    assert offenders == {}, (
        f"unexpected process launch outside the sandbox: {offenders}"
    )


def test_oauth_module_never_writes_to_disk() -> None:
    """C4.2 — the shipped store is in-memory; durability belongs to the host."""
    tree = ast.parse(OAUTH_MODULE.read_text(encoding="utf-8"))
    hits = _scan(tree, calls=WRITE_CALLS, imports=PERSISTENCE_IMPORTS)
    assert hits == set(), f"oauth module must not persist material: {hits}"


# --- negative self-checks ----------------------------------------------------
#
# A guard that has never been observed failing is not evidence. Each of these plants
# exactly the violation its guard exists to catch.


@pytest.mark.parametrize(
    "source",
    [
        "import socket",
        "import webbrowser",
        "from http.server import HTTPServer",
        "import asyncio\nasyncio.start_server(h, '127.0.0.1', 0)",
        "import anyio\nanyio.create_tcp_listener(local_port=0)",
    ],
    ids=["socket", "browser", "http-server", "start-server", "tcp-listener"],
)
def test_listener_guard_actually_rejects(source: str) -> None:
    hits = _scan(
        ast.parse(source),
        calls=LISTENER_AND_BROWSER_CALLS,
        imports=LISTENER_AND_BROWSER_IMPORTS,
    )
    assert hits, "the listener/browser guard failed to flag a real violation"


@pytest.mark.parametrize(
    "source",
    ["import subprocess", "import os\nos.fork()", "from multiprocessing import Pool"],
    ids=["subprocess", "fork", "multiprocessing"],
)
def test_process_guard_actually_rejects(source: str) -> None:
    hits = _scan(ast.parse(source), calls=PROCESS_CALLS, imports=PROCESS_IMPORTS)
    assert hits, "the process-launch guard failed to flag a real violation"


@pytest.mark.parametrize(
    "source",
    [
        "from pathlib import Path\nPath('t').write_text('token')",
        "open('tokens.json', 'w')",
        "import sqlite3",
    ],
    ids=["write-text", "open", "sqlite"],
)
def test_write_guard_actually_rejects(source: str) -> None:
    hits = _scan(ast.parse(source), calls=WRITE_CALLS, imports=PERSISTENCE_IMPORTS)
    assert hits, "the disk-write guard failed to flag a real violation"


def test_host_and_adapter_protocols_declare_the_same_shape() -> None:
    """The host declares its own copy of the two seams so the host→adapters import
    edge stays confined to the single file that already declares it
    (`FILE_SCOPED_RUNTIME_EXCEPTIONS`). Protocols are structural, so the copies work
    — but only while they stay the same shape, which is what this pins.

    Compared on method names and parameter names, not annotations: the host copy
    deliberately types material as opaque `object`, because a layer that cannot read
    it cannot accidentally log it.
    """
    import inspect

    from loopplane.adapters.mcp.oauth import McpAuthorizationHandler, McpTokenStore
    from loopplane.host.capabilities import (
        ManagedMcpAuthorizationHandler,
        ManagedMcpTokenStore,
    )

    for adapter_proto, host_proto in (
        (McpAuthorizationHandler, ManagedMcpAuthorizationHandler),
        (McpTokenStore, ManagedMcpTokenStore),
    ):
        adapter_methods = {
            name
            for name, _ in inspect.getmembers(adapter_proto, inspect.isfunction)
            if not name.startswith("_")
        }
        host_methods = {
            name
            for name, _ in inspect.getmembers(host_proto, inspect.isfunction)
            if not name.startswith("_")
        }
        assert adapter_methods == host_methods, (
            f"{adapter_proto.__name__} and {host_proto.__name__} drifted: "
            f"{adapter_methods ^ host_methods}"
        )
        for name in sorted(adapter_methods):
            adapter_params = list(
                inspect.signature(getattr(adapter_proto, name)).parameters
            )
            host_params = list(inspect.signature(getattr(host_proto, name)).parameters)
            assert adapter_params == host_params, (
                f"{adapter_proto.__name__}.{name} parameters drifted: "
                f"{adapter_params} != {host_params}"
            )


def test_guards_are_not_vacuous_against_the_real_module() -> None:
    """The scanner must actually be reading the OAuth module, not an empty file."""
    tree = ast.parse(OAUTH_MODULE.read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
    assert "build_oauth_auth" in OAUTH_MODULE.read_text(encoding="utf-8")
