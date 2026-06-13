"""The authentication boundary for the web/API host (011).

A pluggable, fail-safe, default-deny verifier enforced before any route reaches
the embedded host (FR-013-FR-015). The host ships no credential store; the
embedder injects an ``Authenticator``. Absent one, the default denies every
request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Header, HTTPException

# A verifier over the request credential (the Authorization header value, or
# ``None`` when absent): truthy admits, falsy denies. A raised exception denies.
Authenticator = Callable[[str | None], Awaitable[bool]]


async def _deny_all(credential: str | None) -> bool:
    """The default authenticator: deny every request (FR-014)."""

    return False


DENY_ALL: Authenticator = _deny_all


def make_auth_dependency(
    authenticator: Authenticator,
) -> Callable[[str | None], Awaitable[None]]:
    """Build the FastAPI dependency that enforces the boundary on a route.

    Denies on a missing / falsy / **raising** verdict, returning a fixed
    ``401`` that never echoes the credential (FR-013-FR-015, NFR-005).
    """

    async def require_auth(
        authorization: str | None = Header(default=None),
    ) -> None:
        try:
            allowed = await authenticator(authorization)
        except Exception:
            allowed = False
        if not allowed:
            raise HTTPException(status_code=401, detail="unauthorized")

    return require_auth
