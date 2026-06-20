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
from loopplane.adapters.mcp.schema import translate_schema
from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import ImageBlock, TextBlock

_CONNECT_TIMEOUT_SECONDS = 15.0


class MCPToolAdapter:
    """Use as an async context manager: connection lifetimes are owned by
    the entering task (FR-041).
    """

    def __init__(self, configs: Sequence[MCPServerConfig]) -> None:
        self._configs = list(configs)
        self._stack = AsyncExitStack()
        self._descriptors: list[ToolDescriptor] = []
        self._tools: dict[
            str, tuple[Any, str]
        ] = {}  # qualified -> (session, remote name)
        self._failures: dict[str, str] = {}
        self._fallback_schemas: list[str] = []

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
                self._failures[config.name] = f"{type(exc).__name__}: {exc}"
            else:
                await self._stack.enter_async_context(server_stack)

    @staticmethod
    async def _safe_aclose(stack: AsyncExitStack) -> None:
        try:
            await stack.aclose()
        except Exception:
            # Cleanup of a failed server must not mask the original failure
            # or abort connecting the remaining servers.
            pass

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
            read, write, _ = await server_stack.enter_async_context(
                streamablehttp_client(config.url)
            )
        elif config.transport == "sse":
            from mcp.client.sse import sse_client

            assert config.url is not None
            read, write = await server_stack.enter_async_context(sse_client(config.url))
        else:
            from mcp.client.websocket import websocket_client

            assert config.url is not None
            read, write = await server_stack.enter_async_context(
                websocket_client(config.url)
            )

        session = await server_stack.enter_async_context(ClientSession(read, write))
        # The timeout may only wrap plain awaits: wrapping the context
        # entries above would interleave cancel scopes across the exit stack.
        with anyio.fail_after(_CONNECT_TIMEOUT_SECONDS):
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

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(self._descriptors)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        session, remote_name = self._tools[name]
        try:
            result = await session.call_tool(remote_name, dict(call_input))
        except Exception as exc:
            yield ErrorOutput(
                category=ErrorCategory.ADAPTER_FAULT,
                message=f"external server call failed: {type(exc).__name__}: {exc}",
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

    async def shutdown(self) -> None:
        await self._stack.aclose()
