"""The authentication boundary for the web/API host (011; identity added in 022).

A pluggable, fail-safe, default-deny verifier enforced before any route reaches
the embedded host (FR-013-FR-015). The verifier maps the request credential (the
Authorization header value) to a ``Principal`` **identity**, or denies. The host
ships no credential store; the embedder injects an ``Authenticator``. Absent one,
the default denies every request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Principal:
    """An authenticated caller's identity — the unit of session ownership (022).

    The ``id`` is opaque; this boundary defines no roles or permissions.
    """

    id: str


# A verifier over the request credential (the Authorization header value, or
# ``None`` when absent): a ``Principal`` admits, ``None`` denies. A raised
# exception denies.
Authenticator = Callable[[str | None], Awaitable[Principal | None]]


async def _deny_all(credential: str | None) -> Principal | None:
    """The default authenticator: deny every request (FR-014)."""

    return None


DENY_ALL: Authenticator = _deny_all


def token_authenticator(tokens: Mapping[str, str]) -> Authenticator:
    """A reference verifier (dev/demo/tests): map a ``Bearer <token>`` value to
    ``Principal(id=tokens[token])``; an unknown, missing, or non-bearer
    credential denies.

    The host stores no credentials — the ``{token: principal_id}`` mapping is
    supplied by the embedder (Constitution VII). Real deployments inject their
    own verifier (OAuth/JWT/etc.).
    """

    mapping = dict(tokens)

    async def verify(credential: str | None) -> Principal | None:
        if credential is None:
            return None
        scheme, _, token = credential.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        principal_id = mapping.get(token)
        return Principal(id=principal_id) if principal_id is not None else None

    return verify


def make_auth_dependency(
    authenticator: Authenticator,
) -> Callable[[str | None], Awaitable[Principal]]:
    """Build the FastAPI dependency that enforces the boundary on a route and
    resolves the caller's ``Principal``.

    Denies on a missing / ``None`` / **raising** verdict, returning a fixed
    ``401`` that never echoes the credential (FR-013-FR-015, NFR-005).
    """

    async def require_principal(
        authorization: str | None = Header(default=None),
    ) -> Principal:
        try:
            principal = await authenticator(authorization)
        except Exception:
            principal = None
        if principal is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        return principal

    return require_principal
