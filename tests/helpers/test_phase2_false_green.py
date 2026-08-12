"""Intentional negative mutations to prevent false-green Phase-2 harnesses (T015)."""

from __future__ import annotations

import pytest
from tests.helpers.desktop_profile import make_profile_root, ownership_lock_contention
from tests.helpers.desktop_sidecar import ByteSplitStdio
from tests.helpers.public_safety import (
    LOOPPLANE_PATH_MARKER,
    LOOPPLANE_SECRET_MARKER,
    SurfacePayload,
    assert_secondary_surface_clean,
    scan_secondary_surfaces,
)


def test_false_green_secondary_must_fail_on_secret() -> None:
    with pytest.raises(AssertionError):
        assert_secondary_surface_clean(
            SurfacePayload(kind="status", text=LOOPPLANE_SECRET_MARKER)
        )


def test_false_green_scan_detects_pid_style_leak() -> None:
    findings = scan_secondary_surfaces(
        [SurfacePayload(kind="log", text="pid leaked lp-synth-pid=424242")]
    )
    assert findings, "expected leak detection"


def test_false_green_scan_detects_private_path_marker() -> None:
    findings = scan_secondary_surfaces(
        [SurfacePayload(kind="log", text=f"path leaked {LOOPPLANE_PATH_MARKER}")]
    )
    assert findings, "expected private-path leak detection"


def test_false_green_byte_split_does_not_return_full_line_when_chunked() -> None:
    io = ByteSplitStdio(read_chunk_size=1)
    io.feed_input("abc\n")
    first = io.readline()
    assert first == b"a"
    assert first != b"abc\n"


def test_false_green_lock_contention_without_acquire_is_false() -> None:
    fx = make_profile_root()
    try:
        assert ownership_lock_contention(fx) is False
    finally:
        fx.cleanup()
