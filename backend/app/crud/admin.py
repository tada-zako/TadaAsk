from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Admin
from app.db.schemas import AdminCreate


class AdminCRUD:
    """管理员账号的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_admin(self, admin_data: AdminCreate) -> Admin:
        """创建新的管理员账号，并返回创建的管理员实例"""
        new_admin = Admin(**admin_data.model_dump())
        self.session.add(new_admin)
        await self.session.flush()  # 获取新管理员的 UID
        return new_admin

    async def get_admin_by_username(self, username: str) -> Admin | None:
        """根据用户名获取管理员实例"""
        result = await self.session.execute(
            select(Admin).where(Admin.username == username)
        )
        return result.scalars().first()

    async def get_primary_admin(self) -> Admin | None:
        """获取最早创建的管理员；MVP 阶段系统只维护一个配置管理员。"""
        result = await self.session.execute(
            select(Admin).order_by(Admin.id.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_credentials(
        self,
        admin: Admin,
        *,
        username: str | None = None,
        password_hash: str | None = None,
    ) -> Admin:
        """更新管理员凭据，并使此前签发的 token 失效。"""
        if username is not None:
            admin.username = username
        if password_hash is not None:
            admin.password_hash = password_hash

        admin.token_version += 1
        await self.session.flush()
        return admin
