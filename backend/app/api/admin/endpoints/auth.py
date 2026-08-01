from typing import Annotated

from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from loguru import logger

from ...deps import AdminCRUDeps, SessionFactoryDeps
from ...schemas import Token, TokenData
from app.core.security import verify_password, create_access_token, decode_access_token
from app.crud import AdminCRUD
from app.db.models import Admin
from app.db.schemas import AdminRead

router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")


def _decode_token_data(token: str) -> TokenData:
    """解码 token 并返回解码后的 TokenData 对象"""
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid authentication credentials"
    )
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    try:
        return TokenData.model_validate(payload)
    except ValidationError as exc:
        raise credentials_exception from exc


async def get_current_admin(
    admin_crud: AdminCRUDeps,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Admin:
    """校验 Admin access token，并确认 token_version 仍然有效。"""
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid authentication credentials"
    )
    token_data = _decode_token_data(token)
    admin = await admin_crud.get_admin_by_username(username=token_data.username)
    if not admin or admin.token_version != token_data.token_version:
        raise credentials_exception
    return admin


async def get_current_admin_factory(
    session_factory: SessionFactoryDeps,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Admin:
    """长连接场景使用短事务完成 Admin token 校验。"""
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid authentication credentials"
    )
    token_data = _decode_token_data(token)

    # 通过即使创建的短连接 session，避免 session 在整个 request 周期内不关闭
    async with session_factory() as session:
        admin_crud = AdminCRUD(session=session)
        admin = await admin_crud.get_admin_by_username(username=token_data.username)

    if not admin or admin.token_version != token_data.token_version:
        raise credentials_exception
    return admin


async def authenticate_admin(
    admin_crud: AdminCRUDeps,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Admin | None:
    """验证管理员用户名和密码"""
    admin = await admin_crud.get_admin_by_username(form_data.username)

    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not admin:
        logger.bind(event="auth.login.failed").warning("Admin login failed")
        raise unauthorized_exception
    if not verify_password(form_data.password, admin.password_hash):
        logger.bind(event="auth.login.failed").warning("Admin login failed")
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
    logger.bind(
        event="auth.login.succeeded",
        admin_uid=admin.uid,
    ).info("Admin login succeeded")
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=AdminRead, summary="Current Admin")
async def get_current_admin_profile(
    admin: Annotated[Admin, Depends(get_current_admin)],
) -> AdminRead:
    """返回当前有效 access token 对应的管理员信息。"""
    return AdminRead.model_validate(admin)
