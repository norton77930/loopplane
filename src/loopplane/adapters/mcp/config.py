"""Layered MCP server configuration (FR-040): more specific layers override
broader ones by server name; a malformed entry disables only itself and is
reported, never crashing the runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    transport: Literal["stdio", "http", "sse", "websocket"]
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    auth_token: str | None = None  # 059 — host-supplied bearer (http/sse); never echoed
    # 084 — the authorization *mode*, never a credential (ADR 0019 D4). `None` is
    # today's behaviour; "interactive" asks the host to authorize a person.
    authorization: Literal["interactive"] | None = None

    @model_validator(mode="after")
    def _check_transport_fields(self) -> MCPServerConfig:
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio transport requires a command")
        if self.transport in ("http", "sse", "websocket") and not self.url:
            raise ValueError(f"{self.transport} transport requires a url")
        if self.authorization is not None:
            # Two credentials would leave "which one wins" to chance; ambiguity in a
            # credential path is a defect, not a convenience (ADR 0019 D4).
            if self.auth_token:
                raise ValueError("authorization and auth_token are mutually exclusive")
            if self.transport not in ("http", "sse"):
                # stdio is a local subprocess with no authorization endpoint;
                # websocket_client accepts neither headers nor auth (ADR 0007 D3).
                raise ValueError(
                    f"{self.transport} transport cannot use interactive authorization"
                )
        return self


def merge_layers(
    layers: Sequence[Mapping[str, Mapping[str, object]]],
) -> tuple[list[MCPServerConfig], list[str]]:
    """Merge configuration layers ordered broadest first; later (more
    specific) layers override by server name. Returns the effective configs
    and the problems found (one per disabled entry).

    A malformed entry disables only itself: it is reported and skipped, and a
    valid same-named definition from a broader layer is left in place rather
    than being discarded.
    """
    effective: dict[str, MCPServerConfig] = {}
    problems: list[str] = []
    for layer in layers:
        for name, raw in layer.items():
            try:
                effective[name] = MCPServerConfig(name=name, **dict(raw))
            except (ValidationError, TypeError) as exc:
                problems.append(
                    f"server entry {name!r} is malformed and skipped: {exc}"
                )
    return list(effective.values()), problems
