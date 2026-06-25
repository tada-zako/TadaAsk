from pathlib import Path
from typing import AsyncIterator
import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from .models import Base
from .fts import init_fts_tables
from app.core.config import PROJECT_ROOT, settings


# 确保数据库文件存在
database_path = Path(settings.sqlite_database_path)
database_path.parent.mkdir(parents=True, exist_ok=True)

ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"
# 异步数据库 URL
DATABASE_URL = f"sqlite+aiosqlite:///{database_path}"

# 异步数据库引擎
engine = create_async_engine(
    url=DATABASE_URL,
    echo=settings.sqlalchemy_echo,
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


def _run_alembic_upgrade() -> None:
    """同步执行 Alembic upgrade"""
    alembic_cfg = Config(str(ALEMBIC_INI_PATH))
    command.upgrade(alembic_cfg, "head")


async def run_migrations() -> None:
    """运行 Alembic schema migration 到最新版本"""
    await asyncio.to_thread(_run_alembic_upgrade)


async def init_db():
    """初始化数据库附属结构；
    NOTE(26-6-25): ORM 普通表由 Alembic migration 管理。"""

    async with engine.begin() as conn:
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
