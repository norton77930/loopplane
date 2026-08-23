"""The MCP Tool Adapter (FR-040–FR-045; research R4).

Confines the `mcp` SDK (an optional extra) behind the Gateway adapter SPI:
connection lifecycle per configured server, source-qualified tool names,
per-server failure isolation, and schema translation with a permissive
fallback. Every external tool is subject to the same Gateway pipeline as an
internal tool (FR-045).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

import anyio

from loopplane.adapters.mcp.config import MCPServerConfig
from loopplane.adapters.mcp.oauth import (
    AUTHORIZATION_FAILED_MESSAGE,
    DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS,
    InMemoryMcpTokenStore,
    McpAuthorizationError,
    McpAuthorizationHandler,
    McpTokenStore,
    build_oauth_auth,
)
from loopplane.adapters.mcp.schema import translate_schema
from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import ImageBlock, TextBlock

_CONNECT_TIMEOUT_SECONDS = 15.0

# 084 — an interactive server's `initialize()` is where the OAuth flow actually
# fires on the http transport, so the 15s connect budget would be the budget for a
# person to open a browser, log in, and consent. It is not enough, and cutting the
# flow short discards the pending `state` and verifier, so a retry starts over.
# The human wait itself is bounded inside `oauth.py` (the SDK's own `timeout` is
# stored and never enforced); this margin only has to be larger than that bound.
_AUTHORIZATION_CONNECT_TIMEOUT_SECONDS = (
    DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS + _CONNECT_TIMEOUT_SECONDS
)

# 059 — input schemas for the synthetic resource tools.
_LIST_RESOURCES_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_READ_RESOURCE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"uri": {"type": "string"}},
    "required": ["uri"],
    "additionalProperties": False,
}


def _auth_headers(config: MCPServerConfig) -> dict[str, str] | None:
    """The host-supplied bearer header for a configured token, or None (059).

    The token is sent only to the transport; it is never logged or surfaced.
    """

    if config.auth_token:
        return {"Authorization": f"Bearer {config.auth_token}"}
    return None


def _is_interactive(config: MCPServerConfig) -> bool:
    """Whether this server authorizes a person rather than presenting a token (084)."""

    return config.authorization == "interactive"


class MCPToolAdapter:
    """Use as an async context manager: connection lifetimes are owned by
    the entering task (FR-041).
    """

    def __init__(
        self,
        configs: Sequence[MCPServerConfig],
        *,
        authorization_handler: McpAuthorizationHandler | None = None,
        token_store: McpTokenStore | None = None,
        principal_id: str | None = None,
    ) -> None:
        # 084 — the two seams are constructor parameters, not RuntimeConfig knobs
        # (ADR 0019 D2): they are host capabilities, and RuntimeConfig must not
        # become a place credentials pass through. Both default to absent, which is
        # what makes a configuration without interactive servers byte-identical.
        self._configs = list(configs)
        self._authorization_handler = authorization_handler
        self._token_store = token_store
        self._principal_id = principal_id
        self._stack = AsyncExitStack()
        self._descriptors: list[ToolDescriptor] = []
        self._tools: dict[
            str, tuple[Any, str]
        ] = {}  # qualified -> (session, remote name)
        # 059 — synthetic resource tools: qualified -> (session, "list" | "read")
        self._resource_tools: dict[str, tuple[Any, str]] = {}
        self._failures: dict[str, str] = {}
        self._fallback_schemas: list[str] = []
        self._fallback_store: McpTokenStore | None = None

    @property
    def connection_failures(self) -> dict[str, str]:
        """Per-server connect failures (FR-043); healthy servers stay available."""
        return dict(self._failures)

    @property
    def fallback_schemas(self) -> list[str]:
        """Qualified names whose schemas degraded to the permissive fallback."""
        return list(self._fallback_schemas)

    async def __aenter__(self) -> MCPToolAdapter:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.shutdown()

    async def connect(self) -> None:
        for config in self._configs:
            # Each server owns its own exit stack so a failed connect releases
            # that server's transport/session immediately, rather than leaving
            # half-open resources on the shared stack until shutdown (FR-043).
            server_stack = AsyncExitStack()
            try:
                await self._connect_one(config, server_stack)
            except Exception as exc:  # isolation per server (FR-043)
                await self._safe_aclose(server_stack)
                self._failures[config.name] = self._failure_text(config, exc)
            else:
                await self._stack.enter_async_context(server_stack)

    @staticmethod
    def _failure_text(config: MCPServerConfig, exc: BaseException) -> str:
        """The per-server failure string, reduced to a fixed message when a
        credential could be inside the exception (084; contract C6.2).

        An ordinary connect failure keeps its detail, which is what makes a
        misconfigured URL diagnosable. An authorization failure does not: the SDK's
        own errors interpolate the ``state`` values it compared, and a token
        endpoint's error body is remote text. Neither may reach a caller who reads
        ``connection_failures`` and logs it.
        """

        if _is_interactive(config) or isinstance(exc, McpAuthorizationError):
            return AUTHORIZATION_FAILED_MESSAGE
        return f"{type(exc).__name__}: {exc}"

    @staticmethod
    async def _safe_aclose(stack: AsyncExitStack) -> None:
        try:
            await stack.aclose()
        except Exception:
            # Cleanup of a failed server must not mask the original failure
            # or abort connecting the remaining servers.
            pass

    async def _transport_auth_kwargs(self, config: MCPServerConfig) -> dict[str, Any]:
        """The auth keyword arguments for the http/sse transport clients.

        Empty for an ordinary server, so the transport call is exactly what it was
        before 084. An interactive server with no host handler raises here rather
        than falling through to an unauthenticated connection — the whole point of
        failing closed is that a missing credential must not become a silent
        misconfiguration (ADR 0019 D7).
        """

        if _is_interactive(config):
            if self._authorization_handler is None:
                raise McpAuthorizationError("no authorization handler is configured")
            assert config.url is not None
            store = self._token_store
            if store is None:
                # Default to process-lifetime storage rather than refusing: the host
                # opted into interactive authorization by supplying a handler, and
                # durability is a separate decision it may legitimately not have made.
                store = self._default_store()
            return {
                "auth": await build_oauth_auth(
                    server_url=config.url,
                    server_name=config.name,
                    principal=self._principal_id,
                    handler=self._authorization_handler,
                    store=store,
                )
            }
        headers = _auth_headers(config)
        return {"headers": headers} if headers else {}

    def _default_store(self) -> McpTokenStore:
        """Create and remember the in-memory store, so one adapter keeps one.

        Cached rather than rebuilt: a fresh store per connect would discard material
        between a connect and a later reconnect within the same adapter.
        """

        if self._fallback_store is None:
            self._fallback_store = InMemoryMcpTokenStore()
        return self._fallback_store

    async def _connect_one(
        self, config: MCPServerConfig, server_stack: AsyncExitStack
    ) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if config.transport == "stdio":
            assert config.command is not None
            parameters = StdioServerParameters(
                command=config.command, args=list(config.args)
            )
            read, write = await server_stack.enter_async_context(
                stdio_client(parameters)
            )
        elif config.transport == "http":
            from mcp.client.streamable_http import streamablehttp_client

            assert config.url is not None
            # 059 — host-supplied bearer on the http transport (never logged).
            # 084 — or the SDK OAuth client, when the server authorizes a person.
            # Both stay absent for an ordinary server, so the call is unchanged.
            kwargs = await self._transport_auth_kwargs(config)
            read, write, _ = await server_stack.enter_async_context(
                streamablehttp_client(config.url, **kwargs)
            )
        elif config.transport == "sse":
            from mcp.client.sse import sse_client

            assert config.url is not None
            kwargs = await self._transport_auth_kwargs(config)  # 059 / 084
            read, write = await server_stack.enter_async_context(
                sse_client(config.url, **kwargs)
            )
        else:
            from mcp.client.websocket import websocket_client

            assert config.url is not None
            # 059 — the SDK websocket_client takes no headers; token auth is not
            # applied to websocket (documented in ADR 0007).
            read, write = await server_stack.enter_async_context(
                websocket_client(config.url)
            )

        session = await server_stack.enter_async_context(ClientSession(read, write))
        # The timeout may only wrap plain awaits: wrapping the context
        # entries above would interleave cancel scopes across the exit stack.
        # 084 — an interactive server needs the wider budget, because the OAuth
        # flow fires inside `initialize()` on the http transport.
        connect_timeout = (
            _AUTHORIZATION_CONNECT_TIMEOUT_SECONDS
            if _is_interactive(config)
            else _CONNECT_TIMEOUT_SECONDS
        )
        with anyio.fail_after(connect_timeout):
            await session.initialize()
            listed = await session.list_tools()
        for tool in listed.tools:
            qualified = f"{config.name}:{tool.name}"
            schema, fell_back = translate_schema(tool.inputSchema)
            if fell_back:
                self._fallback_schemas.append(qualified)
            self._descriptors.append(
                ToolDescriptor(
                    name=qualified,
                    description=tool.description or "",
                    input_schema=schema,
                    source=f"external-server:{config.name}",
                )
            )
            self._tools[qualified] = (session, tool.name)
        # 059 — resources: when the server supports them, surface list/read as
        # Gateway-routed synthetic tools. A server without resource support (the
        # probe raises) registers none and is unaffected (per-server isolation).
        try:
            with anyio.fail_after(_CONNECT_TIMEOUT_SECONDS):
                await session.list_resources()
        except Exception:
            return
        for kind, schema in (
            ("list", _LIST_RESOURCES_SCHEMA),
            ("read", _READ_RESOURCE_SCHEMA),
        ):
            qualified = f"{config.name}:{kind}_resource{'s' if kind == 'list' else ''}"
            if qualified in self._tools:
                # A real server tool already owns this name: do NOT double-register
                # (a duplicate descriptor would crash the whole gateway build,
                # defeating per-server isolation, FR-043). The real tool wins.
                continue
            self._descriptors.append(
                ToolDescriptor(
                    name=qualified,
                    description=(
                        "List the MCP server's resources"
                        if kind == "list"
                        else "Read an MCP server resource by uri"
                    ),
                    input_schema=schema,
                    source=f"external-server:{config.name}",
                )
            )
            self._resource_tools[qualified] = (session, kind)

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(self._descriptors)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        if name in self._resource_tools:
            async for output in self._invoke_resource(name, call_input):
                yield output
            return
        session, remote_name = self._tools[name]
        try:
            result = await session.call_tool(remote_name, dict(call_input))
        except Exception:
            yield ErrorOutput(
                category=ErrorCategory.ADAPTER_FAULT,
                message="external server call failed",
            )
            return

        blocks: list[AdapterOutput] = []
        for item in result.content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                blocks.append(TextBlock(text=text))
                continue
            data = getattr(item, "data", None)
            mime_type = getattr(item, "mimeType", None)
            if isinstance(data, str) and isinstance(mime_type, str):
                blocks.append(ImageBlock(media=data, format=mime_type))

        if result.isError:
            message = "; ".join(
                block.text for block in blocks if isinstance(block, TextBlock)
            )
            yield ErrorOutput(message=message or "external tool reported an error")
            return
        # Preserve the server's original block order (text and image
        # interleaved as returned).
        for block in blocks:
            yield block

    async def _invoke_resource(
        self, name: str, call_input: dict[str, object]
    ) -> AsyncIterator[AdapterOutput]:
        """Dispatch a synthetic resource tool (059) to the session resource APIs.

        Resources reach the model only via the Gateway, as existing tool-result
        blocks (TextBlock/ImageBlock) — no new content type (ADR 0007).
        """

        from pydantic import AnyUrl

        session, kind = self._resource_tools[name]
        try:
            if kind == "list":
                listed = await session.list_resources()
                lines = [
                    f"- {res.uri} — {res.name or ''} — {res.description or ''}".rstrip(
                        " —"
                    )
                    for res in listed.resources
                ]
                yield TextBlock(text="\n".join(lines) if lines else "(no resources)")
                return
            uri = call_input.get("uri")
            if not isinstance(uri, str) or not uri:
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message="read_resource requires a string 'uri'",
                )
                return
            result = await session.read_resource(AnyUrl(uri))
        except Exception:
            yield ErrorOutput(
                category=ErrorCategory.ADAPTER_FAULT,
                message="external server resource call failed",
            )
            return

        for item in result.contents:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                yield TextBlock(text=text)
                continue
            blob = getattr(item, "blob", None)
            mime_type = getattr(item, "mimeType", None)
            if (
                isinstance(blob, str)
                and isinstance(mime_type, str)
                and mime_type.startswith("image/")
            ):
                yield ImageBlock(media=blob, format=mime_type)
            else:
                # Non-image blob: surface a reference rather than inventing a new
                # content type (ADR 0007 — resources stay within existing blocks).
                uri_ref = getattr(item, "uri", "")
                mt = mime_type or "application/octet-stream"
                yield TextBlock(text=f"[resource {uri_ref} ({mt})]")

    async def shutdown(self) -> None:
        await self._stack.aclose()
