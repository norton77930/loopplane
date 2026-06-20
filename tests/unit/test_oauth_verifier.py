"""Offline tests for the OAuth/JWT verifier (056; gap G18).

A locally-generated self-signed RSA keypair + an in-memory JWKS injected by
monkeypatching the resolver's fetch — NO network (NFR-006/007). Covers the positive
path, the full negative matrix (alg=none, HS/RS confusion, wrong iss/aud, expired, nbf,
unknown kid, tampered sig, bad header), claim mapping, fail-closed, and default-off.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest

pytest.importorskip("jwt")
pytest.importorskip("cryptography")

import jwt  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

from loopplane.webapi import auth_jwt, jwt_authenticator  # noqa: E402
from loopplane.webapi.auth import DENY_ALL, Principal  # noqa: E402

pytestmark = pytest.mark.anyio

ISS = "https://issuer.example"
AUD = "loopplane-api"
KID = "test-key"
SUB = "user-123"

_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_WRONG_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_PEM = (
    _PRIVATE.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def _jwk() -> dict[str, Any]:
    jwk = RSAAlgorithm.to_jwk(_PRIVATE.public_key(), as_dict=True)
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return jwk


def _claims(**over: Any) -> dict[str, Any]:
    now = int(time.time())
    claims = {"iss": ISS, "aud": AUD, "sub": SUB, "iat": now, "exp": now + 300}
    claims.update(over)
    return claims


def _encode(
    payload: dict[str, Any],
    *,
    alg: str = "RS256",
    kid: str | None = KID,
    key: Any = None,
) -> str:
    headers = {"kid": kid} if kid is not None else {}
    if alg == "none":
        key = ""
    elif key is None:
        key = _PRIVATE
    return jwt.encode(payload, key, algorithm=alg, headers=headers)


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fetch(self: auth_jwt._JwksResolver) -> list[dict[str, Any]]:
        return [_jwk()]

    monkeypatch.setattr(auth_jwt._JwksResolver, "_fetch_jwks", _fetch)


def _auth(**kw: Any) -> Any:
    return jwt_authenticator(
        issuer=ISS, audience=AUD, jwks_url="https://issuer.example/jwks", **kw
    )


# --- positive ---------------------------------------------------------------


async def test_valid_token_admits_principal() -> None:
    principal = await _auth()(f"Bearer {_encode(_claims())}")
    assert principal == Principal(id=SUB)


async def test_principal_claim_mapping() -> None:
    auth = _auth(principal_claim="email")
    principal = await auth(f"Bearer {_encode(_claims(email='a@b.com'))}")
    assert principal == Principal(id="a@b.com")


async def test_missing_principal_claim_denied() -> None:
    auth = _auth(principal_claim="email")  # token has no email claim
    assert await auth(f"Bearer {_encode(_claims())}") is None


# --- negative matrix --------------------------------------------------------


async def test_alg_none_rejected() -> None:
    assert await _auth()(f"Bearer {_encode(_claims(), alg='none')}") is None


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _forge_hs256(payload: dict[str, Any], secret: str) -> str:
    # A hand-forged HS256 token (PyJWT's own encode refuses an asymmetric key as an
    # HMAC secret) — the HS/RS confusion attack an attacker would actually craft.
    header = {"alg": "HS256", "typ": "JWT", "kid": KID}
    seg = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    sig = hmac.new(secret.encode(), seg.encode(), hashlib.sha256).digest()
    return f"{seg}.{_b64(sig)}"


async def test_hs_rs_confusion_rejected() -> None:
    # HS256 forged with the public key as the HMAC secret — pinned RS256 rejects it.
    token = _forge_hs256(_claims(), _PUBLIC_PEM)
    assert await _auth()(f"Bearer {token}") is None


async def test_wrong_issuer_rejected() -> None:
    assert await _auth()(f"Bearer {_encode(_claims(iss='https://evil'))}") is None


async def test_wrong_audience_rejected() -> None:
    assert await _auth()(f"Bearer {_encode(_claims(aud='other-api'))}") is None


async def test_expired_rejected() -> None:
    now = int(time.time())
    token = _encode(_claims(iat=now - 600, exp=now - 300))
    assert await _auth()(f"Bearer {token}") is None


async def test_not_yet_valid_rejected() -> None:
    assert (
        await _auth()(f"Bearer {_encode(_claims(nbf=int(time.time()) + 9999))}") is None
    )


async def test_unknown_kid_rejected() -> None:
    assert await _auth()(f"Bearer {_encode(_claims(), kid='other-kid')}") is None


async def test_tampered_signature_rejected() -> None:
    # Signed by a different private key than the JWKS advertises for this kid.
    token = _encode(_claims(), key=_WRONG_PRIVATE)
    assert await _auth()(f"Bearer {token}") is None


async def test_bad_headers_rejected() -> None:
    auth = _auth()
    assert await auth(None) is None
    assert await auth("nope") is None
    assert await auth("Basic abc") is None  # non-bearer scheme
    assert await auth("Bearer ") is None  # empty token


# --- fail-closed + default-off ----------------------------------------------


async def test_jwks_fetch_fault_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(self: auth_jwt._JwksResolver) -> list[dict[str, Any]]:
        raise RuntimeError("jwks endpoint down")

    monkeypatch.setattr(auth_jwt._JwksResolver, "_fetch_jwks", _boom)
    assert await _auth()(f"Bearer {_encode(_claims())}") is None


async def test_default_off_denies() -> None:
    # create_app() with no authenticator falls back to DENY_ALL (byte-identical).
    assert await DENY_ALL(f"Bearer {_encode(_claims())}") is None
