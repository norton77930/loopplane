"""Self-tests for desktop profile fixtures (T014 / T015)."""

from __future__ import annotations

from tests.helpers.desktop_profile import (
    acquire_ownership_lock,
    all_writer_reservation,
    make_profile_root,
    ownership_lock_contention,
    release_ownership_lock,
    write_dual_journals,
    write_pristine_absent_states,
    write_unexpected_payload,
)


def test_pristine_absent_uninitialized() -> None:
    fx = make_profile_root()
    try:
        receipt = write_pristine_absent_states(fx)
        assert receipt.checkpoint_state == "absent_uninitialized"
        assert receipt.artifact_state == "absent_uninitialized"
        assert fx.proof_path is not None and fx.proof_path.is_file()
        assert fx.pointer_path is not None and not fx.pointer_path.exists()
    finally:
        fx.cleanup()


def test_ownership_lock_contention() -> None:
    fx = make_profile_root()
    try:
        assert ownership_lock_contention(fx) is False
        acquire_ownership_lock(fx)
        assert ownership_lock_contention(fx) is True
        release_ownership_lock(fx)
        assert ownership_lock_contention(fx) is False
    finally:
        fx.cleanup()


def test_unexpected_payload_and_journals() -> None:
    fx = make_profile_root()
    try:
        bad = write_unexpected_payload(fx)
        assert bad.is_file()
        journals = write_dual_journals(fx)
        assert len(journals) == 2
        assert all(j.is_file() for j in journals)
        lease = all_writer_reservation()
        assert "workspace.revalidate" in lease["rejects"]
    finally:
        fx.cleanup()
