"""Public-safety routing over current Desktop product surfaces (078 T091).

T010 proved the scanner itself distinguishes content from secondary surfaces.
This module routes synthetic markers through the **product** code that renders
each secondary surface — the JSON-RPC dispatcher's error envelope, the fixed
public error catalogue, the backup disclosure, and the portable archive
manifest — and asserts none of them disclose LoopPlane-owned secrets, private
paths, rules, PIDs, or raw errors, while authorized conversation content
survives losslessly inside the archived content entry.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.public_safety import (
    AUTHORIZED_MODEL_CONTENT_MARKER,
    AUTHORIZED_USER_CONTENT_MARKER,
    LOOPPLANE_PATH_MARKER,
    LOOPPLANE_SECRET_MARKER,
    SurfacePayload,
    all_prohibited_secondary_markers,
    assert_content_surface_may_retain,
    assert_secondary_surface_clean,
    scan_secondary_surfaces,
)

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from archive import create_portable_archive, validate_archive  # noqa: E402
from backup import describe_backup  # noqa: E402
from dispatcher import Dispatcher  # noqa: E402
from protocol import (  # noqa: E402
    INTERNAL_FAILURE,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
    PROTOCOL_NAME,
    RUNTIME_EVENT_SCHEMA,
)

INITIALIZE_PARAMS = {
    "protocol": {
        "name": PROTOCOL_NAME,
        "major": PROTOCOL_MAJOR,
        "minor": PROTOCOL_MINOR,
    },
    "runtime_event_schema": RUNTIME_EVENT_SCHEMA,
    "client": {"name": "public-safety-routing", "version": "0"},
    "requested_capabilities": [],
}

POISONED = " | ".join(all_prohibited_secondary_markers())


def _frame(id_: str, method: str, params: dict[str, Any]) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params})


async def _initialized(methods: dict[str, Any]) -> Dispatcher:
    dispatcher = Dispatcher(methods=methods)
    await dispatcher.handle_frame(_frame("init", "initialize", INITIALIZE_PARAMS))
    return dispatcher


@pytest.mark.anyio
async def test_rpc_error_envelope_discloses_no_raw_handler_failure() -> None:
    """A handler failure carrying every prohibited marker must not reach the wire."""

    async def failing(_params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(POISONED)

    # Premise: this exact failure text is detectable on a secondary surface, so a
    # clean envelope below is a real result rather than an unscanned one.
    assert scan_secondary_surfaces([SurfacePayload(kind="rpc_error", text=POISONED)])

    dispatcher = await _initialized({"session.list": failing})
    responses = await dispatcher.handle_frame(_frame("r1", "session.list", {}))

    assert responses, "the dispatcher must answer a failed request"
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))
    assert responses[0]["error"]["data"]["messageKey"] == INTERNAL_FAILURE.message_key


@pytest.mark.anyio
async def test_rpc_error_envelope_discloses_no_marker_bearing_parameters() -> None:
    """Rejected request parameters must not be echoed back onto the error surface."""

    dispatcher = await _initialized({})
    responses = await dispatcher.handle_frame(
        _frame("r2", "session.list", {"private": LOOPPLANE_PATH_MARKER})
    )

    assert responses
    text = json.dumps(responses[0], ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="rpc_error", text=text))


def test_fixed_public_error_catalogue_is_secondary_safe() -> None:
    """Every shipped error envelope is a secondary surface and must stay clean."""

    catalogue = (
        INTERNAL_FAILURE,
        PARSE_ERROR,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        INVALID_PARAMS,
    )
    payloads = [
        SurfacePayload(
            kind="diagnostic", text=json.dumps(error.to_jsonrpc(), ensure_ascii=False)
        )
        for error in catalogue
    ]
    assert scan_secondary_surfaces(payloads) == []


def test_backup_disclosure_is_secondary_safe() -> None:
    disclosure = json.dumps(describe_backup().to_public(), ensure_ascii=False)
    assert_secondary_surface_clean(
        SurfacePayload(kind="backup_manifest", text=disclosure)
    )


def test_archive_routes_authorized_content_without_leaking_into_metadata(
    tmp_path: Path,
) -> None:
    """Authorized conversation text survives in the entry, never in the manifest."""

    snapshot = tmp_path / "snapshot"
    (snapshot / "sessions").mkdir(parents=True)
    conversation = "\n".join(
        (AUTHORIZED_USER_CONTENT_MARKER, AUTHORIZED_MODEL_CONTENT_MARKER)
    )
    # Write bytes, not text: universal newlines would rewrite the separator and
    # make the losslessness assertion below measure the fixture, not the product.
    (snapshot / "sessions" / "checkpoints.sqlite3").write_bytes(
        conversation.encode("utf-8")
    )
    destination = tmp_path / "portable.zip"

    manifest = create_portable_archive(
        destination,
        profile_portable={
            "schema_version": 1,
            "profile_id": "profile-opaque",
            "principal_id": "principal-opaque",
            "projects": [{"id": "project", "label": "Work", "session_ids": ["s"]}],
            "preferences": {"theme": "dark", "composer_draft": LOOPPLANE_SECRET_MARKER},
            "workspace_references": [
                {"id": "workspace", "label": "Docs", "availability": "available"}
            ],
            "credentials": {"token": LOOPPLANE_SECRET_MARKER},
        },
        snapshot_root=snapshot,
        disclosure_acknowledged=True,
    )

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="manifest", text=manifest_text))
    # Authorized content belongs to the entry, not to entry metadata.
    assert AUTHORIZED_USER_CONTENT_MARKER not in manifest_text

    revalidated = json.dumps(validate_archive(destination), ensure_ascii=False)
    assert_secondary_surface_clean(SurfacePayload(kind="manifest", text=revalidated))

    with zipfile.ZipFile(destination, "r") as archive:
        exported_profile = archive.read("profile/profile.json").decode("utf-8")
        restored = archive.read("sessions/checkpoints.sqlite3").decode("utf-8")

    # The unsent draft and the credential are excluded, so the marker cannot ride
    # the exported profile either.
    assert_secondary_surface_clean(
        SurfacePayload(kind="manifest", text=exported_profile)
    )

    content = SurfacePayload(kind="conversation", text=restored)
    assert_content_surface_may_retain(content, AUTHORIZED_USER_CONTENT_MARKER)
    assert_content_surface_may_retain(content, AUTHORIZED_MODEL_CONTENT_MARKER)
    assert restored == conversation, "authorized content must survive losslessly"
