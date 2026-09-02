"""Postgres admission grants (085; ADR 0020 D2). Cross-process-honest only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio

from loopplane.webapi.admission import (
    AdmissionGrant,
    AdmissionRejected,
    reject_if_over,
)

_SCHEMA_PRINCIPALS = (
    "CREATE TABLE IF NOT EXISTS admission_principals (principal_id TEXT PRIMARY KEY)"
)
_SCHEMA_GRANTS = (
    "CREATE TABLE IF NOT EXISTS admission_grants ("
    "grant_id TEXT PRIMARY KEY, "
    "principal_id TEXT NOT NULL, "
    "holder_id TEXT NOT NULL, "
    "expires_at TIMESTAMPTZ NOT NULL, "
    "reserves_outstanding BOOLEAN NOT NULL)"
)


def _require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - simulated absence in tests
        raise RuntimeError(
            "PostgresAdmissionStore requires psycopg; install loopplane[postgres]"
        ) from exc
    return psycopg


class PostgresAdmissionStore:
    def __init__(self, conninfo: str) -> None:
        self._psycopg = _require_psycopg()
        self._conninfo = conninfo
        self._ensure_schema()

    def __repr__(self) -> str:
        return "PostgresAdmissionStore(conninfo=<redacted>)"

    def __str__(self) -> str:
        return "PostgresAdmissionStore(conninfo=<redacted>)"

    def _ensure_schema(self) -> None:
        connection = self._psycopg.connect(self._conninfo)
        try:
            connection.execute(_SCHEMA_PRINCIPALS)
            connection.execute(_SCHEMA_GRANTS)
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> Any:
        return self._psycopg.connect(self._conninfo)

    def _take_sync(
        self,
        principal_id: str,
        holder_id: str,
        in_flight_cap: int,
        outstanding_cap: int | None,
        ttl: timedelta,
    ) -> AdmissionGrant:
        now = datetime.now(UTC)
        grant_id = uuid.uuid4().hex
        expires_at = now + ttl
        reserves_outstanding = outstanding_cap is not None
        connection = self._connect()
        try:
            with connection.transaction():
                connection.execute(
                    "INSERT INTO admission_principals(principal_id) VALUES (%s) "
                    "ON CONFLICT (principal_id) DO NOTHING",
                    (principal_id,),
                )
                connection.execute(
                    "SELECT principal_id FROM admission_principals "
                    "WHERE principal_id = %s FOR UPDATE",
                    (principal_id,),
                )
                connection.execute(
                    "DELETE FROM admission_grants "
                    "WHERE principal_id = %s AND expires_at <= %s",
                    (principal_id, now),
                )
                rows = connection.execute(
                    "SELECT reserves_outstanding "
                    "FROM admission_grants WHERE principal_id = %s",
                    (principal_id,),
                ).fetchall()
                reject_if_over(
                    in_flight=len(rows),
                    outstanding=sum(1 for row in rows if row[0]),
                    in_flight_cap=in_flight_cap,
                    outstanding_cap=outstanding_cap,
                )
                connection.execute(
                    "INSERT INTO admission_grants("
                    "grant_id, principal_id, holder_id, expires_at, "
                    "reserves_outstanding) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        grant_id,
                        principal_id,
                        holder_id,
                        expires_at,
                        reserves_outstanding,
                    ),
                )
        except AdmissionRejected:
            raise
        finally:
            connection.close()
        return AdmissionGrant(
            grant_id=grant_id,
            principal_id=principal_id,
            holder_id=holder_id,
            expires_at=expires_at,
            reserves_outstanding=reserves_outstanding,
        )

    async def take(
        self,
        principal_id: str,
        holder_id: str,
        *,
        in_flight_cap: int,
        outstanding_cap: int | None,
        ttl: timedelta,
    ) -> AdmissionGrant:
        return await anyio.to_thread.run_sync(
            self._take_sync,
            principal_id,
            holder_id,
            in_flight_cap,
            outstanding_cap,
            ttl,
        )

    def _heartbeat_sync(self, grant_id: str, holder_id: str, ttl: timedelta) -> bool:
        now = datetime.now(UTC)
        connection = self._connect()
        try:
            row = connection.execute(
                "UPDATE admission_grants SET expires_at = %s "
                "WHERE grant_id = %s AND holder_id = %s AND expires_at > %s "
                "RETURNING grant_id",
                (now + ttl, grant_id, holder_id, now),
            ).fetchone()
            connection.commit()
        finally:
            connection.close()
        return row is not None

    async def heartbeat(self, grant_id: str, holder_id: str, *, ttl: timedelta) -> bool:
        return await anyio.to_thread.run_sync(
            self._heartbeat_sync, grant_id, holder_id, ttl
        )

    def _release_sync(self, grant_id: str, holder_id: str) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM admission_grants WHERE grant_id = %s AND holder_id = %s",
                (grant_id, holder_id),
            )
            connection.commit()
        finally:
            connection.close()

    async def release(self, grant_id: str, holder_id: str) -> None:
        await anyio.to_thread.run_sync(self._release_sync, grant_id, holder_id)
