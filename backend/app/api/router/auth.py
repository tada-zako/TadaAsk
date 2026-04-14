from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..deps import SessionDeps
from ..schemas import Token
from app.core.security import verify_password, create_access_token
from app.db.models import Admins
from app.crud import admin_crud


router = APIRouter(prefix="/auth", tags=["Admin Authentication"])


async def authenticate_admin(
    session: SessionDeps, username: str, password: str
) -> Admins | None:
    """验证管理员用户名和密码"""
    admin = await admin_crud.get_admin_by_username(session, username)
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


@router.post(
    "/login",
    summary="Admin Login",
    description="Authenticate admin and return access token",
)
async def login(
    session: SessionDeps,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """管理员登录接口：验证用户名和密码，返回 JWT 访问令牌"""
    admin = await authenticate_admin(
        session, username=form_data.username, password=form_data.password
    )
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建 JWT 访问令牌，包含用户名和 token_version
    access_token = create_access_token(
        data={"username": admin.username, "token_version": admin.token_version}
    )
    return Token(access_token=access_token, token_type="bearer")
