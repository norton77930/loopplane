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
    transport: Literal["stdio", "http"]
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None

    @model_validator(mode="after")
    def _check_transport_fields(self) -> MCPServerConfig:
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio transport requires a command")
        if self.transport == "http" and not self.url:
            raise ValueError("http transport requires a url")
        return self


def merge_layers(
    layers: Sequence[Mapping[str, Mapping[str, object]]],
) -> tuple[list[MCPServerConfig], list[str]]:
    """Merge configuration layers ordered broadest first; later (more
    specific) layers override by server name. Returns the effective configs
    and the problems found (one per disabled entry).
    """
    effective: dict[str, MCPServerConfig | None] = {}
    problems: list[str] = []
    for layer in layers:
        for name, raw in layer.items():
            try:
                effective[name] = MCPServerConfig(name=name, **dict(raw))
            except (ValidationError, TypeError) as exc:
                effective[name] = None
                problems.append(
                    f"server entry {name!r} is malformed and disabled: {exc}"
                )
    configs = [config for config in effective.values() if config is not None]
    return configs, problems
