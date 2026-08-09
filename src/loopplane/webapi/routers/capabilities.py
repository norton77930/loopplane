"""Capabilities routes for the WebAPI app factory."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    CapabilityOperationResultView,
    CapabilitySettingsStatusView,
    ManagedMcpConfigurationView,
    ManagedMemoryDetailView,
    ManagedMemoryView,
    ManagedScheduleView,
    ManagedSkillDetailView,
    ManagedSkillView,
    McpConfigurationWriteRequest,
    McpMutationResponse,
    MemoryMutationResponse,
    MemoryWriteRequest,
    ModelDefaultMutationResponse,
    ModelDefaultView,
    ModelDefaultWriteRequest,
    ScheduleMutationResponse,
    ScheduleWriteRequest,
    SkillImportRequest,
    SkillMutationResponse,
    SkillWriteRequest,
    WorkspaceContextMutationResponse,
    WorkspaceContextView,
    WorkspaceContextWriteRequest,
)
from loopplane.webapi.routers.context import RouterState


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    host = state.host
    require = state.require
    catalog = state.catalog

    # --- 075: capability management foundation ------------------------------

    @router.get("/capabilities/settings")
    async def get_capability_settings(
        principal: Principal = Depends(require),
    ) -> CapabilitySettingsStatusView:
        return CapabilitySettingsStatusView.from_status(
            host.capability_settings_status(principal_id=principal.id)
        )

    @router.get("/capabilities/memory")
    async def list_managed_memory(
        principal: Principal = Depends(require),
    ) -> list[ManagedMemoryView]:
        return [
            ManagedMemoryView.from_entry(entry)
            for entry in host.list_managed_memory(principal_id=principal.id)
        ]

    @router.post("/capabilities/memory")
    async def write_managed_memory(
        body: MemoryWriteRequest, principal: Principal = Depends(require)
    ) -> MemoryMutationResponse:
        result = host.write_managed_memory(
            name=body.name,
            kind=body.kind,
            description=body.description,
            content=body.content,
            principal_id=principal.id,
        )
        entry = None
        if result.ok and result.resource_id is not None:
            entry = ManagedMemoryView.from_entry(
                host.get_managed_memory(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return MemoryMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            entry=entry,
        )

    @router.get("/capabilities/memory/{memory_id}")
    async def get_managed_memory(
        memory_id: str, principal: Principal = Depends(require)
    ) -> ManagedMemoryDetailView:
        try:
            return ManagedMemoryDetailView.from_detail(
                host.get_managed_memory(memory_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/memory/{memory_id}")
    async def delete_managed_memory(
        memory_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_memory(
            memory_id,
            confirm=confirm,
            principal_id=principal.id,
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/skills")
    async def list_managed_skills(
        principal: Principal = Depends(require),
    ) -> list[ManagedSkillView]:
        return [
            ManagedSkillView.from_skill(skill)
            for skill in host.list_managed_skills(principal.id)
        ]

    @router.post("/capabilities/skills")
    async def write_managed_skill(
        body: SkillWriteRequest, principal: Principal = Depends(require)
    ) -> SkillMutationResponse:
        result = host.write_managed_skill(
            name=body.name,
            description=body.description,
            instructions=body.instructions,
            principal_id=principal.id,
        )
        skill = None
        if result.ok and result.resource_id is not None:
            skill = ManagedSkillView.from_skill(
                host.get_managed_skill(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return SkillMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            skill=skill,
        )

    @router.post("/capabilities/skills/import")
    async def import_managed_skill(
        body: SkillImportRequest, principal: Principal = Depends(require)
    ) -> SkillMutationResponse:
        result = host.import_managed_skill(
            body.definition,
            principal_id=principal.id,
        )
        skill = None
        if result.ok and result.resource_id is not None:
            skill = ManagedSkillView.from_skill(
                host.get_managed_skill(
                    result.resource_id,
                    principal_id=principal.id,
                )
            )
        return SkillMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            skill=skill,
        )

    @router.get("/capabilities/skills/{skill_id}")
    async def get_managed_skill(
        skill_id: str, principal: Principal = Depends(require)
    ) -> ManagedSkillDetailView:
        try:
            return ManagedSkillDetailView.from_detail(
                host.get_managed_skill(skill_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/skills/{skill_id}")
    async def delete_managed_skill(
        skill_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_skill(
            skill_id,
            confirm=confirm,
            principal_id=principal.id,
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/mcp")
    async def list_managed_mcp(
        principal: Principal = Depends(require),
    ) -> list[ManagedMcpConfigurationView]:
        return [
            ManagedMcpConfigurationView.from_config(config)
            for config in host.list_managed_mcp(principal.id)
        ]

    @router.post("/capabilities/mcp")
    async def upsert_managed_mcp(
        body: McpConfigurationWriteRequest,
        principal: Principal = Depends(require),
    ) -> McpMutationResponse:
        result = await host.upsert_managed_mcp(
            name=body.name,
            transport=body.transport,
            url=body.url,
            command=body.command,
            args=body.args,
            principal_id=principal.id,
        )
        config = next(
            (
                ManagedMcpConfigurationView.from_config(config)
                for config in host.list_managed_mcp(principal.id)
                if config.id == result.resource_id
            ),
            None,
        )
        return McpMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            config=config,
        )

    @router.get("/capabilities/mcp/{mcp_id}")
    async def get_managed_mcp(
        mcp_id: str,
        principal: Principal = Depends(require),
    ) -> ManagedMcpConfigurationView:
        try:
            return ManagedMcpConfigurationView.from_config(
                host.get_managed_mcp(mcp_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.post("/capabilities/mcp/{mcp_id}/reconnect")
    async def reconnect_managed_mcp(
        mcp_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = await host.reconnect_managed_mcp(mcp_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.delete("/capabilities/mcp/{mcp_id}")
    async def delete_managed_mcp(
        mcp_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = await host.delete_managed_mcp(
            mcp_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/contexts")
    async def list_workspace_contexts(
        principal: Principal = Depends(require),
    ) -> list[WorkspaceContextView]:
        return [
            WorkspaceContextView.from_context(context)
            for context in host.list_workspace_contexts(principal.id)
        ]

    @router.post("/capabilities/contexts")
    async def upsert_workspace_context(
        body: WorkspaceContextWriteRequest,
        principal: Principal = Depends(require),
    ) -> WorkspaceContextMutationResponse:
        result = host.upsert_workspace_context(
            name=body.name,
            description=body.description,
            workspace_label=body.workspace_label,
            principal_id=principal.id,
        )
        context = None
        if result.ok and result.resource_id is not None:
            context = WorkspaceContextView.from_context(
                host.get_workspace_context(
                    result.resource_id, principal_id=principal.id
                )
            )
        return WorkspaceContextMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            context=context,
        )

    @router.get("/capabilities/contexts/{context_id}")
    async def get_workspace_context(
        context_id: str,
        principal: Principal = Depends(require),
    ) -> WorkspaceContextView:
        try:
            return WorkspaceContextView.from_context(
                host.get_workspace_context(context_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.delete("/capabilities/contexts/{context_id}")
    async def delete_workspace_context(
        context_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_workspace_context(
            context_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/schedules")
    async def list_managed_schedules(
        principal: Principal = Depends(require),
    ) -> list[ManagedScheduleView]:
        return [
            ManagedScheduleView.from_schedule(schedule)
            for schedule in host.list_managed_schedules(principal.id)
        ]

    @router.post("/capabilities/schedules")
    async def upsert_managed_schedule(
        body: ScheduleWriteRequest,
        principal: Principal = Depends(require),
    ) -> ScheduleMutationResponse:
        result = host.upsert_managed_schedule(
            name=body.name,
            description=body.description,
            trigger=body.trigger,
            instruction=body.instruction,
            enabled=body.enabled,
            principal_id=principal.id,
        )
        schedule = None
        if result.ok and result.resource_id is not None:
            schedule = ManagedScheduleView.from_schedule(
                host.get_managed_schedule(result.resource_id, principal_id=principal.id)
            )
        return ScheduleMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            schedule=schedule,
        )

    @router.get("/capabilities/schedules/{schedule_id}")
    async def get_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> ManagedScheduleView:
        try:
            return ManagedScheduleView.from_schedule(
                host.get_managed_schedule(schedule_id, principal_id=principal.id)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None

    @router.post("/capabilities/schedules/{schedule_id}/run-now")
    async def run_managed_schedule_now(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        try:
            result = host.run_managed_schedule_now(
                schedule_id, principal_id=principal.id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="not found") from None
        return CapabilityOperationResultView.from_result(result)

    @router.post("/capabilities/schedules/{schedule_id}/enable")
    async def enable_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.enable_managed_schedule(schedule_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.post("/capabilities/schedules/{schedule_id}/disable")
    async def disable_managed_schedule(
        schedule_id: str,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.disable_managed_schedule(schedule_id, principal_id=principal.id)
        return CapabilityOperationResultView.from_result(result)

    @router.delete("/capabilities/schedules/{schedule_id}")
    async def delete_managed_schedule(
        schedule_id: str,
        confirm: bool = False,
        principal: Principal = Depends(require),
    ) -> CapabilityOperationResultView:
        result = host.delete_managed_schedule(
            schedule_id, confirm=confirm, principal_id=principal.id
        )
        return CapabilityOperationResultView.from_result(result)

    @router.get("/capabilities/model-default")
    async def get_model_default(
        principal: Principal = Depends(require),
    ) -> ModelDefaultView:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        return ModelDefaultView.from_default(
            host.model_default(
                principal.id,
                available_models=available,
            )
        )

    @router.post("/capabilities/model-default")
    async def set_model_default(
        body: ModelDefaultWriteRequest,
        principal: Principal = Depends(require),
    ) -> ModelDefaultMutationResponse:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        result = host.set_model_default(
            body.model_id,
            available_models=available,
            principal_id=principal.id,
        )
        return ModelDefaultMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            default=ModelDefaultView.from_default(
                host.model_default(
                    principal.id,
                    available_models=available,
                )
            ),
        )

    @router.delete("/capabilities/model-default")
    async def clear_model_default(
        principal: Principal = Depends(require),
    ) -> ModelDefaultMutationResponse:
        available = {model_id: entry.label for model_id, entry in catalog.items()}
        result = host.clear_model_default(principal_id=principal.id)
        return ModelDefaultMutationResponse(
            result=CapabilityOperationResultView.from_result(result),
            default=ModelDefaultView.from_default(
                host.model_default(
                    principal.id,
                    available_models=available,
                )
            ),
        )

    return router
