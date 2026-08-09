"""Inspection routes for the WebAPI app factory."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
)

from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    McpServerView,
    MemoryEntryView,
    SkillsResponse,
    SkillView,
    ToolView,
)
from loopplane.webapi.routers.context import RouterState


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require

    # --- 027: read-only inspection (skills / tools / MCP / memory) ----------

    @router.get("/inspect/skills")
    async def get_skills(principal: Principal = Depends(require)) -> SkillsResponse:
        return SkillsResponse(
            skills=[SkillView.from_info(info) for info in host.inspect_skills()],
            problems=list(host.skill_problems),
        )

    @router.get("/inspect/tools")
    async def get_tools(principal: Principal = Depends(require)) -> list[ToolView]:
        return [ToolView.from_info(info) for info in host.inspect_tools()]

    @router.get("/inspect/mcp")
    async def get_mcp(principal: Principal = Depends(require)) -> list[McpServerView]:
        return [McpServerView.from_info(info) for info in host.inspect_mcp()]

    @router.get("/inspect/memory")
    async def get_memory(
        q: str | None = None, principal: Principal = Depends(require)
    ) -> list[MemoryEntryView]:
        return [MemoryEntryView.from_info(info) for info in host.inspect_memory(q)]

    return router
