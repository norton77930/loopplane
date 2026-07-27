"""Durable owner-scoped capability settings under ``StorageConfig.root``."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from loopplane.host.capabilities import is_valid_managed_mcp_endpoint

_SCHEMA_VERSION: Literal[1] = 1
_LOCKS_GUARD = Lock()
_LOCKS: dict[Path, RLock] = {}
_FORBIDDEN_COMPACT_KEYS = {
    "apikey",
    "authtoken",
    "accesstoken",
    "clientsecret",
    "credential",
    "credentials",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "token",
}
_FORBIDDEN_KEY_PARTS = {
    "authorization",
    "bearer",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}


class CapabilityStoreUnavailable(RuntimeError):
    """The durable settings document could not be read or written safely."""


class CapabilitySettingsState(BaseModel):
    """One principal's durable, browser-safe capability settings."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = _SCHEMA_VERSION
    principal_id: str = Field(min_length=1)
    memory: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    skills: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    mcp: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    contexts: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    schedules: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    model_default: dict[str, JsonValue] | None = None
    updated_at: datetime | None = None


StateMutator = Callable[[CapabilitySettingsState], None]


def _lock_for(path: Path) -> RLock:
    resolved = path.resolve(strict=False)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(resolved, RLock())


def _contains_forbidden_key(value: JsonValue) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = "".join(
                character for character in key.lower() if character.isalnum()
            )
            parts = set(re.split(r"[^a-z0-9]+", key.lower()))
            if (
                normalized in _FORBIDDEN_COMPACT_KEYS
                or parts & _FORBIDDEN_KEY_PARTS
                or _contains_forbidden_key(nested)
            ):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _validate_mcp_endpoint_changes(
    previous: CapabilitySettingsState,
    current: CapabilitySettingsState,
) -> None:
    for mcp_id, record in current.mcp.items():
        previous_record = previous.mcp.get(mcp_id)
        transport = record.get("transport")
        endpoint = record.get("url")
        if previous_record is not None and (
            previous_record.get("transport"),
            previous_record.get("url"),
        ) == (transport, endpoint):
            continue
        if not isinstance(transport, str) or not isinstance(endpoint, str):
            raise CapabilityStoreUnavailable("capability settings unavailable")
        if not is_valid_managed_mcp_endpoint(transport, endpoint):
            raise CapabilityStoreUnavailable("capability settings unavailable")


class CapabilitySettingsStore:
    """Versioned JSON persistence with per-principal atomic updates."""

    def __init__(self, root: Path) -> None:
        self._base = root / "capabilities" / "v1"

    def load(self, principal_id: str) -> CapabilitySettingsState:
        path = self._path(principal_id)
        with _lock_for(path):
            return self._load_unlocked(path, principal_id)

    def update(
        self, principal_id: str, mutator: StateMutator
    ) -> CapabilitySettingsState:
        path = self._path(principal_id)
        with _lock_for(path):
            previous = self._load_unlocked(path, principal_id)
            state = previous.model_copy(deep=True)
            mutator(state)
            _validate_mcp_endpoint_changes(previous, state)
            state.updated_at = datetime.now(UTC)
            self._write_unlocked(path, state)
            return state.model_copy(deep=True)

    def _path(self, principal_id: str) -> Path:
        if not principal_id:
            raise CapabilityStoreUnavailable("capability settings unavailable")
        digest = hashlib.sha256(principal_id.encode("utf-8")).hexdigest()
        return self._base / f"{digest}.json"

    @staticmethod
    def _load_unlocked(path: Path, principal_id: str) -> CapabilitySettingsState:
        if not path.exists():
            return CapabilitySettingsState(principal_id=principal_id)
        try:
            state = CapabilitySettingsState.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise CapabilityStoreUnavailable("capability settings unavailable") from exc
        if state.principal_id != principal_id:
            raise CapabilityStoreUnavailable("capability settings unavailable")
        return state

    def _write_unlocked(self, path: Path, state: CapabilitySettingsState) -> None:
        if _contains_forbidden_key(state.model_dump(mode="json")):
            raise CapabilityStoreUnavailable("capability settings unavailable")
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            temporary.write_text(state.model_dump_json(), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise CapabilityStoreUnavailable("capability settings unavailable") from exc
