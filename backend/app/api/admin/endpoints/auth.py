from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger

from ...deps import AdminCRUDDeps
from ...schemas import Token
from app.core.security import verify_password, create_access_token
from app.db.models import Admin


router = APIRouter()


async def authenticate_admin(
    admin_crud: AdminCRUDDeps,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Admin | None:
    """验证管理员用户名和密码"""
    logger.info(f"Admin 登录尝试，用户名：{form_data.username}")

    admin = await admin_crud.get_admin_by_username(form_data.username)

    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not admin:
        logger.warning(f"Admin 登录失败，用户名不存在：{form_data.username}")
        raise unauthorized_exception
    if not verify_password(form_data.password, admin.password_hash):
        logger.warning(f"Admin 登录失败，密码错误，用户名：{form_data.username}")
        raise unauthorized_exception

    return admin


@router.post(
    "/login",
    summary="Admin Login",
    description="Authenticate admin and return access token",
)
async def login(
    admin: Annotated[Admin, Depends(authenticate_admin)],
) -> Token:
    """管理员登录接口：验证用户名和密码，返回 JWT 访问令牌"""
    # 创建 JWT 访问令牌，包含用户名和 token_version
    access_token = create_access_token(
        data={"username": admin.username, "token_version": admin.token_version}
    )
    logger.info(f"Admin 登录成功，用户名：{admin.username}")
    return Token(access_token=access_token, token_type="bearer")
