"""Desktop public-safety surface assertions (078 T010)."""

from __future__ import annotations

import pytest

from tests.helpers.public_safety import (
    AUTHORIZED_ARTIFACT_MARKER,
    AUTHORIZED_USER_CONTENT_MARKER,
    LOOPPLANE_PATH_MARKER,
    LOOPPLANE_PID_MARKER,
    LOOPPLANE_RAW_ERROR_MARKER,
    LOOPPLANE_RULE_MARKER,
    LOOPPLANE_SECRET_MARKER,
    SurfacePayload,
    assert_content_surface_may_retain,
    assert_secondary_surface_clean,
    scan_secondary_surfaces,
)


def test_secondary_surfaces_reject_loopplane_owned_markers() -> None:
    for kind in ("status", "audit", "rpc_error", "log", "manifest", "diagnostic"):
        clean = SurfacePayload(kind=kind, text="ok: public-safe message")
        assert_secondary_surface_clean(clean)

        for marker in (
            LOOPPLANE_SECRET_MARKER,
            LOOPPLANE_PATH_MARKER,
            LOOPPLANE_RULE_MARKER,
            LOOPPLANE_PID_MARKER,
            LOOPPLANE_RAW_ERROR_MARKER,
        ):
            dirty = SurfacePayload(kind=kind, text=f"error: {marker}")
            with pytest.raises(AssertionError, match="leaked marker"):
                assert_secondary_surface_clean(dirty)


def test_content_surfaces_may_retain_authorized_markers() -> None:
    conv = SurfacePayload(
        kind="conversation",
        text=f"turn: {AUTHORIZED_USER_CONTENT_MARKER}",
    )
    assert_content_surface_may_retain(conv, AUTHORIZED_USER_CONTENT_MARKER)

    art = SurfacePayload(
        kind="eligible_artifact",
        text=AUTHORIZED_ARTIFACT_MARKER,
    )
    assert_content_surface_may_retain(art, AUTHORIZED_ARTIFACT_MARKER)


def test_content_marker_must_not_cross_into_secondary_scan() -> None:
    payloads = [
        SurfacePayload(
            kind="conversation",
            text=AUTHORIZED_USER_CONTENT_MARKER + " " + LOOPPLANE_SECRET_MARKER,
        ),
        SurfacePayload(kind="rpc_error", text="failed safely"),
        SurfacePayload(kind="audit", text=f"bad {LOOPPLANE_PID_MARKER}"),
    ]
    findings = scan_secondary_surfaces(payloads)
    assert any("audit" in f for f in findings)
    assert not any("conversation" in f for f in findings)


def test_assert_helpers_reject_wrong_surface_kind() -> None:
    with pytest.raises(AssertionError, match="secondary kind"):
        assert_secondary_surface_clean(SurfacePayload(kind="conversation", text="x"))
    with pytest.raises(AssertionError, match="content kind"):
        assert_content_surface_may_retain(
            SurfacePayload(kind="status", text=AUTHORIZED_USER_CONTENT_MARKER),
            AUTHORIZED_USER_CONTENT_MARKER,
        )
