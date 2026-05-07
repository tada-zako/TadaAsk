from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Admin
from app.db.schemas import AdminCreate


async def create_admin(session: AsyncSession, admin_data: AdminCreate) -> Admin:
    """创建新的管理员账号，并返回创建的管理员实例"""
    new_admin = Admin(**admin_data.model_dump())
    session.add(new_admin)
    await session.flush()  # 获取新管理员的 UID
    return new_admin


async def get_admin_by_username(session: AsyncSession, username: str) -> Admin | None:
    """根据用户名获取管理员实例"""
    result = await session.execute(select(Admin).where(Admin.username == username))
    return result.scalars().first()
