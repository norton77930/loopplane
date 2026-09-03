"""Postgres turn permits (086; ADR 0021 D2). Same schedule() as in-memory."""

from __future__ import annotations

import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio

from loopplane.fairness_permits import (
    PermitBook,
    PermitWaiter,
    TurnPermit,
    TurnPermitUnavailable,
    schedule,
)

_SCHEMA_META = (
    "CREATE TABLE IF NOT EXISTS turn_meta ("
    "id INTEGER PRIMARY KEY, "
    "last_started TEXT, "
    "consecutive INTEGER NOT NULL)"
)
_SCHEMA_PERMITS = (
    "CREATE TABLE IF NOT EXISTS turn_permits ("
    "permit_id TEXT PRIMARY KEY, "
    "principal_id TEXT NOT NULL, "
    "holder_id TEXT NOT NULL, "
    "expires_at TIMESTAMPTZ NOT NULL)"
)
_SCHEMA_WAITERS = (
    "CREATE TABLE IF NOT EXISTS turn_waiters ("
    "waiter_id TEXT PRIMARY KEY, "
    "principal_id TEXT NOT NULL, "
    "holder_id TEXT NOT NULL, "
    "active_cap INTEGER NOT NULL, "
    "consecutive_cap INTEGER NOT NULL, "
    "ttl_seconds DOUBLE PRECISION NOT NULL, "
    "enqueued_at TIMESTAMPTZ NOT NULL)"
)


class _WouldWait(Exception):
    """Internal: this waiter was not granted yet; async take retries."""


def _require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - simulated absence in tests
        raise RuntimeError(
            "PostgresTurnPermitStore requires psycopg; install loopplane[postgres]"
        ) from exc
    return psycopg


class PostgresTurnPermitStore:
    def __init__(self, conninfo: str) -> None:
        self._psycopg = _require_psycopg()
        self._conninfo = conninfo
        self._ensure_schema()

    def __repr__(self) -> str:
        return "PostgresTurnPermitStore(conninfo=<redacted>)"

    def __str__(self) -> str:
        return "PostgresTurnPermitStore(conninfo=<redacted>)"

    def _ensure_schema(self) -> None:
        connection = self._psycopg.connect(self._conninfo)
        try:
            connection.execute(_SCHEMA_META)
            connection.execute(_SCHEMA_PERMITS)
            connection.execute(_SCHEMA_WAITERS)
            connection.execute(
                "INSERT INTO turn_meta(id, last_started, consecutive) "
                "VALUES (1, NULL, 0) ON CONFLICT (id) DO NOTHING"
            )
            connection.commit()
        except Exception as exc:
            raise TurnPermitUnavailable from exc
        finally:
            connection.close()

    def _connect(self) -> Any:
        try:
            return self._psycopg.connect(self._conninfo)
        except Exception as exc:
            raise TurnPermitUnavailable from exc

    def _load_book(self, connection: Any) -> PermitBook:
        connection.execute("SELECT id FROM turn_meta WHERE id = 1 FOR UPDATE")
        meta = connection.execute(
            "SELECT last_started, consecutive FROM turn_meta WHERE id = 1"
        ).fetchone()
        permit_rows = connection.execute(
            "SELECT permit_id, principal_id, holder_id, expires_at FROM turn_permits"
        ).fetchall()
        waiter_rows = connection.execute(
            "SELECT waiter_id, principal_id, holder_id, active_cap, "
            "consecutive_cap, ttl_seconds, enqueued_at FROM turn_waiters "
            "ORDER BY enqueued_at, waiter_id"
        ).fetchall()
        last_started = meta[0] if meta is not None else None
        consecutive = int(meta[1]) if meta is not None else 0
        permits = {
            row[0]: TurnPermit(
                permit_id=row[0],
                principal_id=row[1],
                holder_id=row[2],
                expires_at=row[3],
            )
            for row in permit_rows
        }
        waiters = [
            PermitWaiter(
                waiter_id=row[0],
                principal_id=row[1],
                holder_id=row[2],
                active_cap=int(row[3]),
                consecutive_cap=int(row[4]),
                ttl=timedelta(seconds=float(row[5])),
                enqueued_at=row[6],
            )
            for row in waiter_rows
        ]
        return PermitBook(
            permits=permits,
            waiters=waiters,
            last_started=last_started,
            consecutive=consecutive,
        )

    def _save_book(self, connection: Any, book: PermitBook) -> None:
        connection.execute("DELETE FROM turn_waiters")
        connection.execute("DELETE FROM turn_permits")
        connection.execute(
            "UPDATE turn_meta SET last_started = %s, consecutive = %s WHERE id = 1",
            (book.last_started, book.consecutive),
        )
        for permit in book.permits.values():
            connection.execute(
                "INSERT INTO turn_permits("
                "permit_id, principal_id, holder_id, expires_at) "
                "VALUES (%s, %s, %s, %s)",
                (
                    permit.permit_id,
                    permit.principal_id,
                    permit.holder_id,
                    permit.expires_at,
                ),
            )
        now = datetime.now(UTC)
        for waiter in book.waiters:
            connection.execute(
                "INSERT INTO turn_waiters("
                "waiter_id, principal_id, holder_id, active_cap, "
                "consecutive_cap, ttl_seconds, enqueued_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    waiter.waiter_id,
                    waiter.principal_id,
                    waiter.holder_id,
                    waiter.active_cap,
                    waiter.consecutive_cap,
                    waiter.ttl.total_seconds(),
                    waiter.enqueued_at or now,
                ),
            )

    def _take_once_sync(
        self,
        waiter_id: str,
        principal_id: str,
        holder_id: str,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ) -> TurnPermit:
        now = datetime.now(UTC)
        connection = self._connect()
        try:
            with connection.transaction():
                book = self._load_book(connection)
                claimed = next(
                    (
                        permit
                        for permit in book.permits.values()
                        if permit.principal_id == principal_id
                        and permit.holder_id == holder_id
                    ),
                    None,
                )
                if claimed is not None:
                    return claimed
                mine = next(
                    (
                        waiter
                        for waiter in book.waiters
                        if waiter.waiter_id == waiter_id
                    ),
                    None,
                )
                if mine is None:
                    book.waiters.append(
                        PermitWaiter(
                            waiter_id=waiter_id,
                            principal_id=principal_id,
                            holder_id=holder_id,
                            active_cap=active_cap,
                            consecutive_cap=consecutive_cap,
                            ttl=ttl,
                            enqueued_at=now,
                        )
                    )
                    mine = book.waiters[-1]
                schedule(book, now)
                self._save_book(connection, book)
                if mine.permit is not None:
                    return mine.permit
        except TurnPermitUnavailable:
            raise
        except _WouldWait:
            raise
        except Exception as exc:
            raise TurnPermitUnavailable from exc
        finally:
            connection.close()
        raise _WouldWait

    def _cancel_waiter_sync(self, waiter_id: str) -> None:
        connection = self._connect()
        try:
            with connection.transaction():
                book = self._load_book(connection)
                book.waiters = [
                    waiter for waiter in book.waiters if waiter.waiter_id != waiter_id
                ]
                schedule(book, datetime.now(UTC))
                self._save_book(connection, book)
        except TurnPermitUnavailable:
            raise
        except Exception as exc:
            raise TurnPermitUnavailable from exc
        finally:
            connection.close()

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        active_cap: int,
        consecutive_cap: int,
        ttl: timedelta,
    ) -> TurnPermit:
        if active_cap < 1 or consecutive_cap < 1:
            raise ValueError("caps must be >= 1")
        waiter_id = uuid.uuid4().hex
        try:
            while True:
                try:
                    return await anyio.to_thread.run_sync(
                        self._take_once_sync,
                        waiter_id,
                        principal_id,
                        holder_id,
                        active_cap,
                        consecutive_cap,
                        ttl,
                    )
                except _WouldWait:
                    await anyio.sleep(0.02)
        except BaseException:
            with suppress(TurnPermitUnavailable):
                await anyio.to_thread.run_sync(self._cancel_waiter_sync, waiter_id)
            raise

    def _heartbeat_sync(self, permit_id: str, holder_id: str, ttl: timedelta) -> bool:
        now = datetime.now(UTC)
        connection = self._connect()
        try:
            row = connection.execute(
                "UPDATE turn_permits SET expires_at = %s "
                "WHERE permit_id = %s AND holder_id = %s AND expires_at > %s "
                "RETURNING permit_id",
                (now + ttl, permit_id, holder_id, now),
            ).fetchone()
            connection.commit()
        except TurnPermitUnavailable:
            raise
        except Exception as exc:
            raise TurnPermitUnavailable from exc
        finally:
            connection.close()
        return row is not None

    async def heartbeat(
        self, permit_id: str, holder_id: str, *, ttl: timedelta
    ) -> bool:
        return await anyio.to_thread.run_sync(
            self._heartbeat_sync, permit_id, holder_id, ttl
        )

    def _release_sync(self, permit_id: str, holder_id: str) -> None:
        connection = self._connect()
        try:
            with connection.transaction():
                book = self._load_book(connection)
                permit = book.permits.get(permit_id)
                if permit is None or permit.holder_id != holder_id:
                    return
                book.permits.pop(permit_id, None)
                schedule(book, datetime.now(UTC))
                self._save_book(connection, book)
        except TurnPermitUnavailable:
            raise
        except Exception as exc:
            raise TurnPermitUnavailable from exc
        finally:
            connection.close()

    async def release(self, permit_id: str, holder_id: str) -> None:
        await anyio.to_thread.run_sync(self._release_sync, permit_id, holder_id)
