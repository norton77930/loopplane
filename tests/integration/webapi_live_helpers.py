"""Shared helpers for 074 web live-channel integration tests."""

from __future__ import annotations


def bearer(token: str) -> dict[str, str]:
    """Return an Authorization header for web API TestClient calls."""

    return {"Authorization": f"Bearer {token}"}
