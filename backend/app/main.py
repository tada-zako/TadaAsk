from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from app.core.db import init_db
from app.router.chat import router as chat_router
from app.router.knowledge_base import router as kb_router
from app.router.workspace import router as workspace_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器，
    负责在应用启动时初始化数据库连接
    """

    logger.info("Starting up the application...")
    await init_db()  # 初始化数据库连接
    yield  # 让应用继续运行
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
app.include_router(chat_router)
app.include_router(kb_router)
app.include_router(workspace_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
