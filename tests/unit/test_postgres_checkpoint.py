"""Unit 060 backend-specific checks for PostgresCheckpointStore: the psycopg
import-guard (deferred to construction) + the DSN is never echoed.

The cross-backend contract PARITY (append/load ordering, round-trip, corrupt-row
skipping, listing, set_title, delete, concurrent appends) is proven by the shared
suite in tests/contract/test_checkpoint_sqlite.py, which now includes a 'postgres'
backend over the offline psycopg stub (tests/pg_stub.py).
"""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from loopplane.checkpoint import postgres as pg_module


def test_construct_without_psycopg_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate psycopg being absent. This also proves the import is DEFERRED to
    # construction (a module-top-level import would have already succeeded before the
    # patch, and __init__ would not re-import, so no RuntimeError would be raised).
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "psycopg":
            raise ImportError("simulated: psycopg not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        pg_module.PostgresCheckpointStore("postgresql://x/db")


def test_dsn_is_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("psycopg")
    from tests import pg_stub

    pg_stub.patch_psycopg(monkeypatch)
    dsn = "postgresql://user:do-not-echo-pw@host/db"
    store = pg_module.PostgresCheckpointStore(dsn)
    assert "do-not-echo-pw" not in repr(store)
    assert "do-not-echo-pw" not in str(store)
