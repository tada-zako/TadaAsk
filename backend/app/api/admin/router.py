from fastapi import APIRouter

from .endpoints import auth, project, chat, knowledge_base

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Admin Authentication"])
router.include_router(project.router, prefix="/project", tags=["Project"])
router.include_router(
    knowledge_base.router, prefix="/knowledge-base", tags=["Knowledge-Base"]
)
router.include_router(chat.router, tags=["Chat"])
