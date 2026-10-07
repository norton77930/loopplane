"""Offline tests for the 067 JWKS unknown-kid refresh hardening.

A counting fake ``_fetch_jwks`` (NO network) + an injected deterministic clock exercise
``_JwksResolver.get_key``: the cross-request throttle (a random-kid spray ⇒ ≤ 1 upstream
fetch per interval), single-flight (a concurrent burst ⇒ one fetch), the preserved
legitimate path (a known cached kid ⇒ no fetch; a TTL-expiry / cold-start refresh always
runs; a real rotation is resolved by the first throttle-permitted refresh), and the
bounded negative-kid cache. Public-safe: a throttled/rejected kid yields ``None``.
"""

from __future__ import annotations

from typing import Any

import anyio
import pytest

from loopplane.webapi import auth_jwt

pytestmark = pytest.mark.anyio


class _Clock:
    """A manually-advanced monotonic clock."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


def _make(
    monkeypatch: pytest.MonkeyPatch,
    *,
    kids: list[str],
    refresh_min_interval: float = 60.0,
    cache_ttl: int = 3600,
) -> tuple[auth_jwt._JwksResolver, dict[str, int], _Clock, dict[str, list[str]]]:
    """A resolver whose ``_fetch_jwks`` returns a fake key per kid + counts the calls.

    Keys are plain strings (the throttle/cache logic never interprets the key material),
    so no PyJWK/cryptography is needed.
    """

    counter = {"n": 0}
    state = {"kids": list(kids)}

    async def _fetch(self: auth_jwt._JwksResolver) -> list[dict[str, Any]]:
        counter["n"] += 1
        return [{"kid": k, "kty": "oct"} for k in state["kids"]]

    # Build the key map directly (skip real PyJWK) — the fake stays key-material-free.
    async def _refresh(self: auth_jwt._JwksResolver) -> None:
        raw = await self._fetch_jwks()
        self._keys = {jwk["kid"]: f"key-{jwk['kid']}" for jwk in raw if jwk.get("kid")}
        now = self._now()
        self._expiry = now + self._cache_ttl
        self._last_refresh = now

    monkeypatch.setattr(auth_jwt._JwksResolver, "_fetch_jwks", _fetch)
    monkeypatch.setattr(auth_jwt._JwksResolver, "_refresh", _refresh)
    clock = _Clock()
    resolver = auth_jwt._JwksResolver(
        jwks_url="https://idp.example/jwks",
        issuer="https://idp.example",
        http_timeout=5.0,
        cache_ttl=cache_ttl,
        refresh_min_interval=refresh_min_interval,
        clock=clock,
    )
    return resolver, counter, clock, state


# --- the legitimate path is preserved ---------------------------------------


async def test_known_cached_kid_is_a_zero_fetch_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, counter, _clock, _state = _make(monkeypatch, kids=["k1"])
    assert await resolver.get_key("k1") == "key-k1"  # cold-start fetch (1)
    assert counter["n"] == 1
    for _ in range(10):
        assert await resolver.get_key("k1") == "key-k1"  # cache hits, no fetch
    assert counter["n"] == 1


async def test_cold_start_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver, counter, _clock, _state = _make(monkeypatch, kids=["k1"])
    assert counter["n"] == 0
    assert await resolver.get_key("k1") == "key-k1"
    assert counter["n"] == 1


async def test_expired_cache_refreshes_not_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, counter, clock, _state = _make(
        monkeypatch, kids=["k1"], cache_ttl=100, refresh_min_interval=3600
    )
    assert await resolver.get_key("k1") == "key-k1"
    assert counter["n"] == 1
    clock.t += 101  # past the cache TTL → expired
    assert await resolver.get_key("k1") == "key-k1"  # a TTL refresh, not throttled
    assert counter["n"] == 2


# --- the spray is bounded ----------------------------------------------------


async def test_unknown_kid_spray_is_throttled_to_one_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fresh cache + a large interval: a spray of distinct unknown kids triggers ≤ 1
    # network refresh (the first allowed), the rest are rejected with no fetch.
    resolver, counter, _clock, _state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=3600, cache_ttl=3600
    )
    assert await resolver.get_key("k1") == "key-k1"  # seed the fresh cache (fetch 1)
    assert counter["n"] == 1
    for i in range(50):
        assert await resolver.get_key(f"bogus-{i}") is None
    assert counter["n"] == 1  # the spray added zero fetches (throttled)


async def test_concurrent_unknown_kid_burst_is_single_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cold start + a large interval: a concurrent burst of distinct unknown kids shares
    # ONE refresh (single-flight lock + re-check), not one fetch each.
    resolver, counter, _clock, _state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=3600
    )
    results: list[Any] = []

    async def _ask(kid: str) -> None:
        results.append(await resolver.get_key(kid))

    async with anyio.create_task_group() as tg:
        for i in range(25):
            tg.start_soon(_ask, f"bogus-{i}")
    assert counter["n"] == 1  # exactly one fetch for the whole burst
    assert all(r is None for r in results)


# --- a real rotation is still resolved (after the throttle interval) ---------


async def test_rotation_resolved_after_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, counter, clock, state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=60, cache_ttl=3600
    )
    assert await resolver.get_key("k1") == "key-k1"  # fetch 1
    assert counter["n"] == 1
    # The IdP rotates in a new kid while the cache is still fresh.
    state["kids"] = ["k1", "k2"]
    # Within the throttle interval: the new kid is rejected without a fetch.
    assert await resolver.get_key("k2") is None
    assert counter["n"] == 1
    # After the interval elapses: the first unknown-kid request refreshes + resolves it.
    clock.t += 61
    assert await resolver.get_key("k2") == "key-k2"
    assert counter["n"] == 2


# --- the negative cache is bounded ------------------------------------------


async def test_throttled_unconfirmed_miss_does_not_block_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A miss recorded while the throttle skipped _refresh must not outlive the
    # throttle and hide a kid the next permitted refresh would have resolved.
    resolver, counter, clock, state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=60, cache_ttl=3600
    )
    assert await resolver.get_key("k1") == "key-k1"
    assert counter["n"] == 1
    clock.t += 30
    assert await resolver.get_key("k2") is None
    assert counter["n"] == 1
    state["kids"] = ["k1", "k2"]
    clock.t += 31  # 61s after the last refresh: the throttle permits one fetch
    assert await resolver.get_key("k1") == "key-k1"
    assert counter["n"] == 1  # a known cached kid does not fetch
    assert await resolver.get_key("k2") == "key-k2"
    assert counter["n"] == 2


async def test_negative_cache_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver, _counter, _clock, _state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=3600, cache_ttl=3600
    )
    await resolver.get_key("k1")  # seed a fresh cache
    for i in range(auth_jwt._NEGATIVE_CACHE_CAP + 500):
        assert await resolver.get_key(f"bogus-{i}") is None
    assert len(resolver._negative) <= auth_jwt._NEGATIVE_CACHE_CAP


async def test_negative_cache_short_circuits_repeat_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, counter, _clock, _state = _make(
        monkeypatch, kids=["k1"], refresh_min_interval=3600, cache_ttl=3600
    )
    await resolver.get_key("k1")  # fetch 1
    assert (
        await resolver.get_key("ghost") is None
    )  # confirmed absent (still fetch 1, throttled)
    base = counter["n"]
    for _ in range(10):
        assert await resolver.get_key("ghost") is None  # negative-cache fast path
    assert counter["n"] == base  # no extra fetches


# --- public-safety -----------------------------------------------------------


async def test_empty_kid_returns_none_without_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, counter, _clock, _state = _make(monkeypatch, kids=["k1"])
    assert await resolver.get_key(None) is None
    assert await resolver.get_key("") is None
    assert counter["n"] == 0
