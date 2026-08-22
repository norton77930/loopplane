"""Interactive MCP authorization (unit 084; gap G12 tail; ADR 0019).

Unit 059 could send a bearer token the embedder already held. This module adds the
other half: obtaining one, for a server that authorizes a *person*.

The protocol itself is the MCP SDK's — :class:`mcp.client.auth.OAuthClientProvider`
performs PKCE, discovery, dynamic client registration, token exchange, refresh, and
the constant-time ``state`` comparison. What this module owns is the boundary around
it (ADR 0019 D1):

* **The host presents the URL and receives the redirect.** Nothing here opens a
  browser, spawns a process, or binds a listening socket — a runtime is frequently a
  headless server process, and one that reaches for a browser breaks there (D3). The
  host even supplies the redirect URI, because only the host knows where its own
  callback lands.
* **The host owns durability.** The only store shipped is
  :class:`InMemoryMcpTokenStore`; no code in this package writes authorization
  material to disk under any configuration (D3).
* **Isolation is per ``(principal, server)``.** Every store call carries both, so one
  principal can never read another's material and no server inherits another's (D5).

Absent a handler the feature fails closed: the server does not connect and no
unauthenticated attempt is made (D7). Renewal is the deliberate exception — given
valid refresh material the SDK renews without calling the handler, which is what
keeps unattended and scheduled work running.

The ``mcp`` SDK is an optional extra, so it is imported inside the function that
needs it: importing this module does not require ``loopplane[mcp]``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - typing only
    import httpx

__all__ = [
    "AUTHORIZATION_FAILED_MESSAGE",
    "AuthorizationResult",
    "InMemoryMcpTokenStore",
    "McpAuthorizationError",
    "McpAuthorizationHandler",
    "McpTokenStore",
    "StoredAuthorizationMaterial",
    "build_oauth_auth",
]

# The SDK's own default is 300s; naming it here keeps the bound visible at the
# boundary rather than buried in a positional argument.
DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS = 300.0

# The single message any authorization failure is reduced to before it can reach a
# caller. The SDK's own errors interpolate the values it compared, and a token
# endpoint's error body is attacker-influenced; neither may become an exception
# string that lands in a log or a traceback (Constitution VII; contract C6.2).
AUTHORIZATION_FAILED_MESSAGE = "interactive authorization failed"

_REDACTED = "<redacted>"


class McpAuthorizationError(Exception):
    """An interactive authorization could not be completed.

    Carries a fixed, public-safe message only. It never embeds a code, token, or
    ``state`` value: an exception string reaches logs and tracebacks, which is
    exactly the path Constitution VII exists to close.
    """


@dataclass(frozen=True)
class AuthorizationResult:
    """What the host got back from the redirect.

    The ``state`` is handed straight to the SDK, which compares it in constant time
    against the value it put in the authorization URL and fails the flow on any
    mismatch. Each flow issues a fresh ``state``, so a replayed redirect finds
    nothing to match.
    """

    code: str
    state: str | None = None

    def __repr__(self) -> str:
        # A default dataclass repr would print the authorization code into any
        # traceback that happens to include this object.
        return f"AuthorizationResult(code={_REDACTED}, state={_REDACTED})"

    __str__ = __repr__


@dataclass
class StoredAuthorizationMaterial:
    """Durable authorization material for one ``(principal, server)`` pair.

    ``tokens`` and ``client_info`` are the SDK's own models, kept opaque here: this
    module stores and returns them without inspecting their contents, so nothing in
    the runtime has a reason to format them.
    """

    tokens: Any | None = None
    client_info: Any | None = None
    # Absolute expiry (unix seconds) of the access token, recorded when it was
    # issued. The SDK tracks expiry only in memory: its ``_initialize`` restores the
    # tokens and the client info from storage but not the expiry time, so a process
    # that restarts would consider a long-dead token valid, send it, take a 401, and
    # then run a **full re-authorization** — a browser prompt — rather than the
    # silent refresh the refresh token exists for. Persisting the expiry alongside
    # the tokens is what lets a restarted scheduled job renew unattended (FR-008).
    expires_at: float | None = None

    def __repr__(self) -> str:
        return (
            "StoredAuthorizationMaterial("
            f"tokens={_REDACTED if self.tokens is not None else None}, "
            f"client_info={_REDACTED if self.client_info is not None else None}, "
            f"expires_at={self.expires_at})"
        )

    __str__ = __repr__


class McpAuthorizationHandler(Protocol):
    """The host's half of an interactive authorization (ADR 0019 D1).

    Supplying no handler is a valid, and the *default*, configuration: it means this
    process cannot authorize interactively, and a server that requires it fails
    closed rather than degrading to an unauthenticated connection.
    """

    def redirect_uri(self, *, server: str) -> str:
        """Where this host's callback will receive the redirect.

        The runtime cannot know this — it does not listen — so the host declares it.
        """

    async def present(self, url: str, *, server: str, principal: str | None) -> None:
        """Show or open the authorization URL. The runtime never does this itself."""

    async def await_result(
        self, *, server: str, principal: str | None
    ) -> AuthorizationResult:
        """Return what the redirect delivered. The runtime never listens for it."""


class McpTokenStore(Protocol):
    """Where authorization material lives — the host's decision (ADR 0019 D3).

    Every operation is keyed by ``(principal, server)``: that pair *is* the
    isolation unit, so an implementation must not collapse it to the server alone.
    """

    async def load(
        self, *, principal: str | None, server: str
    ) -> StoredAuthorizationMaterial | None:
        """Return stored material, or ``None`` when there is none."""

    async def save(
        self,
        *,
        principal: str | None,
        server: str,
        material: StoredAuthorizationMaterial,
    ) -> None:
        """Persist material, including after a refresh."""

    async def discard(self, *, principal: str | None, server: str) -> None:
        """Forget material. Succeeds when nothing is stored, revealing nothing."""


@dataclass
class InMemoryMcpTokenStore:
    """The only store this package ships: process-lifetime, nothing on disk.

    A restart therefore requires authorizing again unless the host supplied a
    durable store of its own. That is the deliberate default (ADR 0019 D3) — a
    runtime that silently persisted credentials would be making a decision that
    belongs to whoever deploys it.
    """

    _entries: dict[tuple[str | None, str], StoredAuthorizationMaterial] = field(
        default_factory=dict
    )

    async def load(
        self, *, principal: str | None, server: str
    ) -> StoredAuthorizationMaterial | None:
        return self._entries.get((principal, server))

    async def save(
        self,
        *,
        principal: str | None,
        server: str,
        material: StoredAuthorizationMaterial,
    ) -> None:
        self._entries[(principal, server)] = material

    async def discard(self, *, principal: str | None, server: str) -> None:
        # Absent material is not an error: a sign-out must not double as a probe for
        # whether a given principal ever authorized a given server.
        self._entries.pop((principal, server), None)

    def __repr__(self) -> str:
        return f"InMemoryMcpTokenStore(entries={len(self._entries)})"

    __str__ = __repr__


def _absolute_expiry(tokens: Any) -> float | None:
    """Turn the SDK token's relative ``expires_in`` into an absolute instant.

    Returns ``None`` when the server did not say — an unknown expiry must stay
    unknown rather than becoming a guess that expires a working token.
    """

    expires_in = getattr(tokens, "expires_in", None)
    if not isinstance(expires_in, int):
        return None
    return time.time() + expires_in


class _StoreBridge:
    """Adapts an :class:`McpTokenStore` to the SDK's four-method ``TokenStorage``.

    The SDK's protocol is keyed by nothing — one instance serves one server — so the
    ``(principal, server)`` pair is bound here, at construction, rather than being
    threaded through the SDK.
    """

    def __init__(
        self, store: McpTokenStore, *, principal: str | None, server: str
    ) -> None:
        self._store = store
        self._principal = principal
        self._server = server

    async def _material(self) -> StoredAuthorizationMaterial:
        found = await self._store.load(principal=self._principal, server=self._server)
        return found if found is not None else StoredAuthorizationMaterial()

    async def get_tokens(self) -> Any | None:
        return (await self._material()).tokens

    async def set_tokens(self, tokens: Any) -> None:
        material = await self._material()
        material.tokens = tokens
        material.expires_at = _absolute_expiry(tokens)
        await self._store.save(
            principal=self._principal, server=self._server, material=material
        )

    async def get_client_info(self) -> Any | None:
        return (await self._material()).client_info

    async def set_client_info(self, client_info: Any) -> None:
        material = await self._material()
        material.client_info = client_info
        await self._store.save(
            principal=self._principal, server=self._server, material=material
        )


async def build_oauth_auth(
    *,
    server_url: str,
    server_name: str,
    principal: str | None,
    handler: McpAuthorizationHandler,
    store: McpTokenStore,
    timeout: float = DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS,
) -> httpx.Auth:
    """Build the SDK OAuth client bound to this host's handler and store.

    The returned object is an ``httpx.Auth`` and is passed straight to the SDK's
    ``streamablehttp_client`` / ``sse_client`` ``auth=`` parameter — the same two
    transports that already accept ``headers=`` for the 059 static token. It is not
    usable on ``stdio`` (no authorization endpoint) or ``websocket`` (the SDK
    transport accepts neither ``headers`` nor ``auth``; ADR 0007 D3).

    Raises :class:`McpAuthorizationError` — always with
    :data:`AUTHORIZATION_FAILED_MESSAGE` or another fixed string — when the ``mcp``
    extra is absent or the host's redirect URI is unusable, so the caller can contain
    the failure per-server rather than crashing the whole adapter build.
    """

    try:
        from mcp.client.auth import OAuthClientProvider
        from mcp.shared.auth import OAuthClientMetadata
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise McpAuthorizationError(
            "interactive MCP authorization requires the 'mcp' extra"
        ) from exc

    from pydantic import AnyUrl, ValidationError

    redirect = (handler.redirect_uri(server=server_name) or "").strip()
    if not redirect:
        raise McpAuthorizationError("host supplied no redirect uri")

    async def redirect_handler(url: str) -> None:
        await handler.present(url, server=server_name, principal=principal)

    async def callback_handler() -> tuple[str, str | None]:
        result = await handler.await_result(server=server_name, principal=principal)
        if not result.code:
            # Fail before handing an empty code to the token endpoint, so the
            # failure reads as "the host returned nothing" rather than as a remote
            # error whose body we would then have to suppress.
            raise McpAuthorizationError("host returned no authorization code")
        return result.code, result.state

    try:
        metadata = OAuthClientMetadata(
            client_name="LoopPlane",
            redirect_uris=[AnyUrl(redirect)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        )
    except (ValidationError, ValueError) as exc:
        raise McpAuthorizationError("host supplied an invalid redirect uri") from exc

    provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=metadata,
        storage=_StoreBridge(store, principal=principal, server=server_name),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        timeout=timeout,
    )

    # Restore the expiry the SDK does not restore itself, so a process that comes
    # back to previously-authorized material takes the refresh branch instead of
    # optimistically sending a dead token, collecting a 401, and prompting a person
    # (FR-008). Guarded rather than assumed: if a future SDK drops the field, the
    # behaviour degrades to that optimistic path rather than raising.
    material = await store.load(principal=principal, server=server_name)
    if material is not None and material.expires_at is not None:
        context = getattr(provider, "context", None)
        if context is not None and hasattr(context, "token_expiry_time"):
            context.token_expiry_time = material.expires_at
    return provider
