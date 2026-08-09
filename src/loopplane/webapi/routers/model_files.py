"""Model Files routes for the WebAPI app factory."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from loopplane.webapi.auth import (
    Principal,
)
from loopplane.webapi.models import (
    ModelInfo,
    UploadResult,
)
from loopplane.webapi.routers.context import RouterState
from loopplane.webapi.uploads import UploadTooLarge


def build_router(state: RouterState) -> APIRouter:
    router = APIRouter(prefix=state.api_prefix)
    catalog = state.catalog
    uploads = state.uploads
    require = state.require

    # --- 028: model catalog + file uploads ----------------------------------

    @router.get("/models")
    async def list_models(
        principal: Principal = Depends(require),
    ) -> list[ModelInfo]:
        return [
            ModelInfo(
                id=mid,
                label=entry.label,
                accepts_media=entry.accepts_media,
                supports_structured_output=entry.supports_structured_output,
            )
            for mid, entry in catalog.items()
        ]

    @router.post("/uploads")
    async def upload_file(
        request: Request,
        name: str = "upload",
        principal: Principal = Depends(require),
    ) -> UploadResult:
        if uploads is None:
            raise HTTPException(status_code=404, detail="uploads not configured")
        data = await request.body()
        try:
            stored = uploads.save(principal.id, name, data)
        except UploadTooLarge as exc:
            raise HTTPException(status_code=413, detail="upload too large") from exc
        return UploadResult(reference=stored.reference, name=stored.name)

    return router
