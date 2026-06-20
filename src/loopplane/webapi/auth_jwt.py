"""A host-supplied OAuth/JWT/OIDC verifier for the web/API host (056; gap G18).

A new :class:`~loopplane.webapi.auth.Authenticator` implementation that validates a
bearer JWT against a JWKS (signature by ``kid`` + issuer + audience + ``exp``/``nbf``,
with **pinned asymmetric algorithms** — ``alg=none`` and HS/RS confusion are rejected
by construction) and maps a configured claim to a ``Principal``.

It sits behind the EXISTING unit-022 ``Authenticator`` seam (``create_app(authenticator=
…)``); no runtime/principal/contract change. The host ships no IdP, no keys, and no
credential store — discovery URL / issuer / audience are embedder-supplied. Any failure
(bad header, unknown ``kid``, signature/claim failure, JWKS-fetch fault, any exception)
denies — returning ``None`` so ``make_auth_dependency`` yields the fixed 401 that never
echoes the credential.

The heavy dependencies (PyJWT + httpx) are **import-guarded**: importing this module
(and ``loopplane.webapi``) does not require them; constructing
:func:`jwt_authenticator` raises a clear error when the ``loopplane[oauth]`` extra is
absent. Requires ``pip install loopplane[oauth]``.
"""

from __future__ import annotations

import time
from typing import Any

from loopplane.webapi.auth import Authenticator, Principal

__all__ = ["jwt_authenticator"]

_DEFAULT_ALGORITHMS = ("RS256",)


class _JwksResolver:
    """Resolve a JWKS signing key by ``kid``, with a TTL cache + a single bounded
    refresh on an unknown ``kid``. Fetches over ``httpx`` (OIDC discovery when no
    explicit ``jwks_url`` is given). The fetch is isolated in :meth:`_fetch_jwks` so
    tests can supply an in-memory JWKS without any network call.
    """

    def __init__(
        self,
        *,
        jwks_url: str | None,
        issuer: str,
        http_timeout: float,
        cache_ttl: int,
    ) -> None:
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._http_timeout = http_timeout
        self._cache_ttl = cache_ttl
        self._keys: dict[str, Any] = {}
        self._expiry = 0.0

    async def get_key(self, kid: str | None) -> Any | None:
        if not kid:
            return None
        if kid in self._keys and time.monotonic() < self._expiry:
            return self._keys[kid]
        await self._refresh()
        return self._keys.get(kid)

    async def _refresh(self) -> None:
        import jwt

        raw = await self._fetch_jwks()
        keys: dict[str, Any] = {}
        for jwk in raw:
            kid = jwk.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = jwt.PyJWK.from_dict(jwk).key
            except Exception:
                continue
        self._keys = keys
        self._expiry = time.monotonic() + self._cache_ttl

    async def _fetch_jwks(self) -> list[dict[str, Any]]:
        import httpx

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            uri = self._jwks_url
            if uri is None:
                meta = (
                    await client.get(
                        f"{self._issuer.rstrip('/')}/.well-known/openid-configuration"
                    )
                ).json()
                uri = meta["jwks_uri"]
            data = (await client.get(uri)).json()
        keys = data.get("keys", [])
        return [k for k in keys if isinstance(k, dict)]


def jwt_authenticator(
    *,
    issuer: str,
    audience: str | list[str],
    jwks_url: str | None = None,
    algorithms: list[str] | None = None,
    principal_claim: str = "sub",
    leeway: int = 60,
    cache_ttl: int = 3600,
    http_timeout: float = 5.0,
) -> Authenticator:
    """Build an :class:`~loopplane.webapi.auth.Authenticator` that verifies an
    OAuth/JWT/OIDC bearer token.

    ``issuer``/``audience`` are validated against the token's ``iss``/``aud``;
    ``jwks_url`` is the JWKS endpoint (OIDC-discovered from ``issuer`` when ``None``);
    ``algorithms`` are the **pinned asymmetric** signature algorithms (default
    ``["RS256"]`` — never ``"none"`` or an ``HS*`` algorithm); ``principal_claim``
    is the claim mapped to ``Principal.id`` (default ``sub``); ``leeway`` is the
    ``exp``/``nbf`` clock-skew tolerance (seconds); ``cache_ttl`` bounds the JWKS cache.

    Requires the ``oauth`` extra; raises ``RuntimeError`` if it is not installed.
    """

    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "jwt_authenticator requires the 'oauth' extra: pip install loopplane[oauth]"
        ) from exc

    pinned = list(algorithms) if algorithms else list(_DEFAULT_ALGORITHMS)
    resolver = _JwksResolver(
        jwks_url=jwks_url,
        issuer=issuer,
        http_timeout=http_timeout,
        cache_ttl=cache_ttl,
    )

    async def verify(credential: str | None) -> Principal | None:
        if credential is None:
            return None
        scheme, _, token = credential.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            header = jwt.get_unverified_header(token)
            key = await resolver.get_key(header.get("kid"))
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key=key,
                algorithms=pinned,
                audience=audience,
                issuer=issuer,
                leeway=leeway,
                options={"require": ["exp", "iss", "aud"]},
            )
        except Exception:
            return None
        principal_id = claims.get(principal_claim)
        if not principal_id:
            return None
        return Principal(id=str(principal_id))

    return verify
