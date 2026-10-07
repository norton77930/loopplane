"""Optional durable weighted turns; isolated from 086 coordination state (087)."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

import anyio

from loopplane.fairness_permits import TurnPermit, TurnPermitUnavailable
from loopplane.fairness_weighted import (
    WeightedTurnPolicy,
    _Book,
    _PollingStore,
    _Request,
)

__all__ = ["WeightedPostgresTurnPermitStore"]

_T = TypeVar("_T")
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS weighted_turn_state ("
    "id INTEGER PRIMARY KEY, policy TEXT NOT NULL, state TEXT NOT NULL)"
)


class _PolicyMismatch(ValueError):
    pass


def _require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError:
        raise RuntimeError(
            "WeightedPostgresTurnPermitStore requires loopplane[postgres]"
        ) from None
    return psycopg


def _encode(book: _Book) -> str:
    return json.dumps(
        {
            "waiters": [
                [w.holder_id, w.tenant, w.expires_at.isoformat(), w.ttl.total_seconds()]
                for w in book.waiters
            ],
            "permits": [
                [p.permit_id, p.principal_id, p.holder_id, p.expires_at.isoformat()]
                for p in book.permits.values()
            ],
            "scores": book.scores,
            "last": book.last,
            "consecutive": book.consecutive,
        },
        separators=(",", ":"),
    )


def _decode(payload: str) -> _Book:
    value = json.loads(payload)
    return _Book(
        waiters=[
            _Request(
                row[0],
                row[1],
                datetime.fromisoformat(row[2]),
                timedelta(seconds=row[3]),
            )
            for row in value["waiters"]
        ],
        permits={
            row[0]: TurnPermit(row[0], row[1], row[2], datetime.fromisoformat(row[3]))
            for row in value["permits"]
        },
        scores=value["scores"],
        last=value["last"],
        consecutive=value["consecutive"],
    )


class WeightedPostgresTurnPermitStore(_PollingStore):
    """Static-policy scheduling domain in one database; no mixed legacy workers."""

    def __init__(self, conninfo: str, *, policy: WeightedTurnPolicy) -> None:
        super().__init__(policy)
        self._driver = _require_psycopg()
        self._conninfo = conninfo
        self._canonical = json.dumps(
            {
                "weights": dict(policy.weights),
                "active_cap": policy.active_cap,
                "consecutive_cap": policy.consecutive_cap,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        self._ensure_schema()

    def __repr__(self) -> str:
        return "WeightedPostgresTurnPermitStore(<redacted>)"

    def _connect(self) -> Any:
        try:
            return self._driver.connect(
                self._conninfo,
                connect_timeout=5,
                options="-c statement_timeout=5000 -c lock_timeout=5000",
            )
        except Exception:
            raise TurnPermitUnavailable("weighted turn store unavailable") from None

    def _check(self, row: Any) -> str:
        if row is None:
            raise TurnPermitUnavailable("weighted turn store unavailable")
        if row[0] != self._canonical:
            raise _PolicyMismatch("weighted turn policy mismatch")
        return str(row[1])

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            with connection.transaction():
                connection.execute(_SCHEMA)
                connection.execute(
                    "INSERT INTO weighted_turn_state(id, policy, state) "
                    "VALUES (1, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (self._canonical, _encode(_Book())),
                )
                row = connection.execute(
                    "SELECT policy, state FROM weighted_turn_state "
                    "WHERE id = 1 FOR UPDATE"
                ).fetchone()
                self._check(row)
        except (_PolicyMismatch, TurnPermitUnavailable):
            raise
        except Exception:
            raise TurnPermitUnavailable("weighted turn store unavailable") from None
        finally:
            with suppress(Exception):
                connection.close()

    def _mutate_sync(self, operation: Callable[[_Book, datetime], _T]) -> _T:
        connection = self._connect()
        application_error = False
        try:
            with connection.transaction():
                row = connection.execute(
                    "SELECT policy, state FROM weighted_turn_state "
                    "WHERE id = 1 FOR UPDATE"
                ).fetchone()
                payload = self._check(row)
                book = _decode(payload)
                try:
                    result = operation(book, datetime.now(UTC))
                except Exception:
                    application_error = True
                    raise
                connection.execute(
                    "UPDATE weighted_turn_state SET state = %s WHERE id = 1",
                    (_encode(book),),
                )
                return result
        except (_PolicyMismatch, TurnPermitUnavailable):
            raise
        except Exception:
            if application_error:
                raise
            raise TurnPermitUnavailable("weighted turn store unavailable") from None
        finally:
            with suppress(Exception):
                connection.close()

    async def _mutate(self, operation: Callable[[_Book, datetime], _T]) -> _T:
        return await anyio.to_thread.run_sync(self._mutate_sync, operation)
