from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from app.core.config import settings
from app.core.security import get_password_hash
from app.db import init_db
from app.db.config import async_session
from app.db.schemas import AdminCreate
from app.crud import admin_crud
from app.api.router import auth_router, chat_router, kb_router, workspace_router


async def valid_or_create_admin():
    """在应用启动时验证是否存在管理员账号，如果不存在则创建一个默认管理员"""
    async with async_session() as session:
        async with session.begin():  # 开启事务
            existing_admin = await admin_crud.get_admin_by_username(
                session, username=settings.admin_username
            )
            if existing_admin:
                logger.info(f"管理员账号已存在，用户名：{settings.admin_username}")

                # TODO: 检查 ADMIN_PASSWORD 是否与现有管理员密码一致，
                # 如果不一致则更新密码（不一定要实现）

                return

            password_hash = get_password_hash(settings.admin_password)

            default_admin_data = AdminCreate(
                username=settings.admin_username,
                password_hash=password_hash,
            )
            new_admin = await admin_crud.create_admin(session, default_admin_data)
            logger.info(f"默认管理员账号已创建，用户名：{new_admin.username}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器，
    负责在应用启动时初始化数据库连接
    """

    logger.info("Starting up the application...")
    await init_db()  # 初始化数据库连接

    # MVP 实现：在应用启动时验证管理员账号，如果不存在则创建一个默认管理员
    await valid_or_create_admin()

    yield  # 运行应用

    # await drop_db()  # 应用关闭时清理数据库连接
    logger.info("Shutting down the application...")


app = FastAPI(lifespan=lifespan, title="LLM Technology Assignment API")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    logger.warning(f"业务异常：{exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler_override(
    request: Request, exc: StarletteHTTPException
):
    logger.warning(f"HTTP异常：{exc.detail}，请求路径：{request.url.path}")
    return await http_exception_handler(request, exc)  # 调用默认的 HTTP 异常处理


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"未处理异常：{exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# 注册路由
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(kb_router)
app.include_router(workspace_router)
# app.include_router(agent_router)    # Agent 功能尚未完全开发，暂不注册


@app.get("/")
async def root():
    return {"message": "Hello World"}
