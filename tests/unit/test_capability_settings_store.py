"""076 durable owner-scoped capability settings store coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopplane.host.capability_store import (
    CapabilitySettingsStore,
    CapabilityStoreUnavailable,
)


def test_capability_state_round_trips_without_principal_in_filename(tmp_path) -> None:
    store = CapabilitySettingsStore(tmp_path)
    saved = store.update(
        "owner@example.invalid",
        lambda state: state.memory.update(
            {"pref": {"id": "pref", "name": "pref", "content": "likes tabs"}}
        ),
    )

    assert saved.memory["pref"]["content"] == "likes tabs"
    restored = CapabilitySettingsStore(tmp_path).load("owner@example.invalid")
    assert restored.memory == saved.memory
    paths = list((tmp_path / "capabilities" / "v1").glob("*.json"))
    assert len(paths) == 1
    assert "owner" not in paths[0].name


def test_capability_store_rejects_credential_like_fields(tmp_path) -> None:
    store = CapabilitySettingsStore(tmp_path)

    with pytest.raises(CapabilityStoreUnavailable) as error:
        store.update(
            "owner",
            lambda state: state.mcp.update(
                {"docs": {"id": "docs", "auth_token": "not-persisted"}}
            ),
        )

    assert str(error.value) == "capability settings unavailable"
    assert store.load("owner").mcp == {}


@pytest.mark.parametrize(
    "field_name",
    ["client_secret", "access_token", "authorization"],
)
def test_capability_store_rejects_nested_sensitive_key_variants(
    tmp_path, field_name: str
) -> None:
    store = CapabilitySettingsStore(tmp_path)

    with pytest.raises(CapabilityStoreUnavailable):
        store.update(
            "owner",
            lambda state: state.mcp.update(
                {"docs": {"id": "docs", "metadata": {field_name: "not-persisted"}}}
            ),
        )

    assert store.load("owner").mcp == {}


@pytest.mark.parametrize(
    ("transport", "url"),
    [
        ("http", "https://user@example.invalid/mcp"),
        ("http", "https://example.invalid/mcp?mode=sample"),
        ("http", "https://example.invalid/mcp#section"),
        ("http", "wss://example.invalid/mcp"),
        ("websocket", "https://example.invalid/mcp"),
        ("sse", "https://example.invalid:invalid/mcp"),
    ],
)
def test_capability_store_rejects_structurally_unsafe_mcp_updates(
    tmp_path: Path,
    transport: str,
    url: str,
) -> None:
    store = CapabilitySettingsStore(tmp_path)

    with pytest.raises(CapabilityStoreUnavailable) as error:
        store.update(
            "owner",
            lambda state: state.mcp.update(
                {
                    "docs": {
                        "id": "docs",
                        "name": "docs",
                        "transport": transport,
                        "url": url,
                        "status": "disconnected",
                    }
                }
            ),
        )

    assert str(error.value) == "capability settings unavailable"
    assert url not in str(error.value)
    assert store.load("owner").mcp == {}


def test_legacy_unsafe_mcp_endpoint_can_load_update_status_and_delete(
    tmp_path: Path,
) -> None:
    store = CapabilitySettingsStore(tmp_path)
    store.update(
        "owner",
        lambda state: state.mcp.update(
            {
                "docs": {
                    "id": "docs",
                    "name": "docs",
                    "transport": "http",
                    "url": "https://example.invalid/mcp",
                    "status": "connected",
                    "tools": ["docs:lookup"],
                    "tool_count": 1,
                }
            }
        ),
    )
    [document] = (tmp_path / "capabilities" / "v1").glob("*.json")
    payload = json.loads(document.read_text(encoding="utf-8"))
    payload["mcp"]["docs"]["url"] = "https://example.invalid/mcp?legacy=credential"
    document.write_text(json.dumps(payload), encoding="utf-8")

    assert store.load("owner").mcp["docs"]["status"] == "connected"
    updated = store.update(
        "owner",
        lambda state: state.mcp["docs"].update(
            {"status": "failed", "tools": [], "tool_count": 0}
        ),
    )
    assert updated.mcp["docs"]["status"] == "failed"

    with pytest.raises(CapabilityStoreUnavailable):
        store.update(
            "owner",
            lambda state: state.mcp["docs"].update(
                {"url": "https://example.invalid/mcp#replacement"}
            ),
        )

    deleted = store.update("owner", lambda state: state.mcp.pop("docs"))
    assert deleted.mcp == {}


def test_capability_store_corruption_is_public_safe(tmp_path) -> None:
    store = CapabilitySettingsStore(tmp_path)
    store.update("owner", lambda state: state.contexts.update({"docs": {"id": "docs"}}))
    [document] = (tmp_path / "capabilities" / "v1").glob("*.json")
    document.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CapabilityStoreUnavailable) as error:
        store.load("owner")

    assert str(error.value) == "capability settings unavailable"
    assert str(tmp_path) not in str(error.value)


def test_capability_store_failed_replace_keeps_previous_document(
    tmp_path, monkeypatch
) -> None:
    store = CapabilitySettingsStore(tmp_path)
    store.update("owner", lambda state: state.memory.update({"first": {"id": "first"}}))

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("private path and credential detail")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(CapabilityStoreUnavailable) as error:
        store.update(
            "owner", lambda state: state.memory.update({"second": {"id": "second"}})
        )

    assert str(error.value) == "capability settings unavailable"
    assert set(store.load("owner").memory) == {"first"}
    assert list((tmp_path / "capabilities" / "v1").glob("*.tmp")) == []
