from fastapi import APIRouter

from .endpoints import chat

router = APIRouter()

router.include_router(chat.router, tags=["Chat"])
