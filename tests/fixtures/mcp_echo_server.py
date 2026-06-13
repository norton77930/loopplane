"""A minimal MCP server used as a test fixture (stdio transport)."""

from mcp.server.fastmcp import FastMCP

server = FastMCP("test-server")


@server.tool()
def mcp_echo(text: str) -> str:
    """Echo the given text back with a server prefix."""
    return f"mcp says: {text}"


@server.tool()
def mcp_fail(text: str) -> str:
    """Always report a tool-level error."""
    raise ValueError(f"server-side failure for {text}")


if __name__ == "__main__":
    server.run()
