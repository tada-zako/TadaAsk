from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .endpoints import auth, project, chat, session as session_endpoints, source
from ..deps import SessionDeps
from ..schemas import TokenData
from app.db.models import Admin
from app.crud import admin_crud
from app.core.security import decode_access_token

router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")


async def get_current_admin(
    session: SessionDeps,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Admin:
    """获取当前登录的管理员实例，基于 JWT 令牌进行鉴权"""
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid authentication credentials"
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    token_data = TokenData.model_validate(payload)
    if not token_data.username:
        raise credentials_exception

    admin = await admin_crud.get_admin_by_username(
        session, username=token_data.username
    )
    if not admin or admin.token_version != token_data.token_version:
        raise credentials_exception
    return admin


router.include_router(auth.router, prefix="/auth", tags=["Admin Authentication"])
router.include_router(
    project.router,
    prefix="/project",
    tags=["Project"],
    dependencies=[Depends(get_current_admin)],
)
router.include_router(
    source.router,
    prefix="/knowledge-base",
    tags=["Knowledge-Base"],
    dependencies=[Depends(get_current_admin)],
)
router.include_router(
    chat.router, tags=["Chat"], dependencies=[Depends(get_current_admin)]
)
router.include_router(
    session_endpoints.router,
    tags=["Session"],
    dependencies=[Depends(get_current_admin)],
)
