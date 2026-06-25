from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from .models import Base
from .fts import init_fts_tables
from app.core.config import settings


# 确保数据库文件存在
database_path = Path(settings.sqlite_path)
database_path.parent.mkdir(parents=True, exist_ok=True)

# 异步数据库 URL
DATABASE_URL = f"sqlite+aiosqlite:///{database_path}"  # 使用 SQLite 数据库

# 异步数据库引擎
engine = create_async_engine(
    url=DATABASE_URL,
    echo=True,  # 打印 SQL 语句
)


@event.listens_for(engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """监听 SQLite 连接事件，启用外键支持"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 异步会话工厂
async_session = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 SQLAlchemy 异步会话工厂"""
    return async_session


async def init_db():
    """初始化 SQLAlchemy 数据库连接并创建表"""

    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await init_fts_tables(conn)  # 初始化 FTS5 虚表及相关触发器


async def drop_db():
    """删除 SQLAlchemy 数据库表"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    获取 SQLAlchemy 异步会话，
    用于 FastAPI 依赖注入
    """
    async with async_session() as session:
        async with session.begin():  # 开启事务，确保 session 在请求结束时正确提交或回滚
            yield session
