from fastapi import APIRouter, Depends

from .endpoints import (
    auth,
    project,
    chat,
    chat_stream,
    model_profile,
    session as session_endpoints,
    source,
    source_sse,
)
from .endpoints.auth import get_current_admin, get_current_admin_factory

router = APIRouter()


router.include_router(auth.router, prefix="/auth", tags=["Admin Authentication"])
router.include_router(
    project.router,
    prefix="/project",
    tags=["Project"],
    dependencies=[Depends(get_current_admin)],
)
router.include_router(
    source.router,
    prefix="/source",
    tags=["Source"],
    dependencies=[Depends(get_current_admin)],
)
router.include_router(
    source_sse.router,
    prefix="/source",
    tags=["Source", "SSE"],
    dependencies=[Depends(get_current_admin_factory)],
)
router.include_router(
    model_profile.router,
    prefix="/model-profile",
    tags=["Model Profile"],
    dependencies=[Depends(get_current_admin)],
)
router.include_router(
    chat.router, tags=["Chat"], dependencies=[Depends(get_current_admin)]
)
router.include_router(
    chat_stream.router,
    tags=["Chat", "SSE"],
    dependencies=[Depends(get_current_admin_factory)],
)
router.include_router(
    session_endpoints.router,
    tags=["Session"],
    dependencies=[Depends(get_current_admin)],
)
