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
from collections.abc import Callable
from typing import Any

import anyio

from loopplane.webapi.auth import Authenticator, Principal

__all__ = ["jwt_authenticator"]

_DEFAULT_ALGORITHMS = ("RS256",)

# 067: the default minimum seconds between unknown-kid-driven JWKS refreshes (the
# cross-request throttle). Default-safe: bounds a random-kid spray to <= 1 upstream
# fetch per interval while keeping key-rotation detection latency <= ~this interval.
_DEFAULT_REFRESH_MIN_INTERVAL = 60.0

# 067: a hard cap on the negative-kid cache so a spray of DISTINCT unknown kids cannot
# grow it without bound (entries also expire; see ``_remember_absent``).
_NEGATIVE_CACHE_CAP = 1024


class _JwksResolver:
    """Resolve a JWKS signing key by ``kid``, with a TTL cache + a bounded refresh on
    an unknown ``kid``. Fetches over ``httpx`` (OIDC discovery when no explicit
    ``jwks_url`` is given). The fetch is isolated in :meth:`_fetch_jwks` so tests can
    supply an in-memory JWKS without any network call.

    **067 hardening** — an unknown ``kid`` no longer triggers an upstream fetch per
    request (which let a random-kid spray amplify IdP fetches unbounded). The
    unknown-kid-driven refresh is bounded by a **cross-request throttle**
    (``refresh_min_interval``: at most one such refresh per interval), serialized by a
    **single-flight** lock (a concurrent burst shares one refresh), with a short bounded
    **negative-kid cache** that short-circuits a recently-confirmed-absent kid. The
    legitimate path is preserved: a known cached ``kid`` is byte-identical (no fetch);
    a TTL-expiry / cold-start refresh always runs (never throttled); a real new ``kid``
    after a key rotation is resolved by the first refresh the throttle permits.
    """

    def __init__(
        self,
        *,
        jwks_url: str | None,
        issuer: str,
        http_timeout: float,
        cache_ttl: int,
        refresh_min_interval: float = _DEFAULT_REFRESH_MIN_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._http_timeout = http_timeout
        self._cache_ttl = cache_ttl
        self._refresh_min_interval = refresh_min_interval
        self._now = clock  # injectable monotonic clock (default time.monotonic)
        self._keys: dict[str, Any] = {}
        self._expiry = 0.0
        self._last_refresh = 0.0
        self._refresh_lock = anyio.Lock()
        # 067: kid -> monotonic expiry of a "confirmed absent" entry (bounded).
        self._negative: dict[str, float] = {}

    async def get_key(self, kid: str | None) -> Any | None:
        if not kid:
            return None
        now = self._now()
        # Legit cache hit — byte-identical to pre-067 (no lock, no fetch).
        if kid in self._keys and now < self._expiry:
            return self._keys[kid]
        # Fresh-cache negative-cache hit — a recently-confirmed-absent kid is rejected
        # without taking the lock or fetching (the spray fast path).
        if now < self._expiry and self._negative.get(kid, 0.0) > now:
            return None
        async with self._refresh_lock:  # single-flight
            now = self._now()
            # Re-check: another coroutine may have refreshed while we waited.
            if kid in self._keys and now < self._expiry:
                return self._keys[kid]
            cache_expired = now >= self._expiry
            # A TTL-expiry / cold-start refresh always runs; an unknown-kid refresh on a
            # still-fresh cache is throttled to <= 1 per ``refresh_min_interval``.
            if (
                cache_expired
                or (now - self._last_refresh) >= self._refresh_min_interval
            ):
                await self._refresh()
                if kid in self._keys:
                    return self._keys[kid]
                # Confirmed absent by this refresh. A throttled miss (no refresh)
                # must not be cached: that entry would outlive the throttle and
                # hide a kid the next permitted refresh would resolve.
                self._remember_absent(kid, self._now())
            return None

    def _remember_absent(self, kid: str, now: float) -> None:
        """Record ``kid`` as confirmed-absent until the next permitted refresh; keep the
        negative cache BOUNDED so a spray of distinct kids cannot grow it unbounded."""
        self._negative[kid] = now + self._refresh_min_interval
        if len(self._negative) > _NEGATIVE_CACHE_CAP:
            # Evict expired entries; if still over the cap, clear it. (The throttle, not
            # this cache, is the load-bearing bound — clearing is cheap and safe.)
            self._negative = {k: exp for k, exp in self._negative.items() if exp > now}
            if len(self._negative) > _NEGATIVE_CACHE_CAP:
                self._negative.clear()

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
        now = self._now()
        self._expiry = now + self._cache_ttl
        self._last_refresh = now

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
    refresh_min_interval: float = _DEFAULT_REFRESH_MIN_INTERVAL,
) -> Authenticator:
    """Build an :class:`~loopplane.webapi.auth.Authenticator` that verifies an
    OAuth/JWT/OIDC bearer token.

    ``issuer``/``audience`` are validated against the token's ``iss``/``aud``;
    ``jwks_url`` is the JWKS endpoint (OIDC-discovered from ``issuer`` when ``None``);
    ``algorithms`` are the **pinned asymmetric** signature algorithms (default
    ``["RS256"]`` — never ``"none"`` or an ``HS*`` algorithm); ``principal_claim``
    is the claim mapped to ``Principal.id`` (default ``sub``); ``leeway`` is the
    ``exp``/``nbf`` clock-skew tolerance (seconds); ``cache_ttl`` bounds the JWKS cache.
    ``refresh_min_interval`` (default 60s, **default-safe**) bounds the unknown-``kid``
    JWKS refresh so a random-kid spray cannot amplify upstream IdP fetches — at most one
    such refresh per interval (the legitimate path is unaffected); set it very large to
    effectively disable the throttle.

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
        refresh_min_interval=refresh_min_interval,
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
