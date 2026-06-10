from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelProfile
from app.db.schemas import ModelProfileCreate


class ModelProfileCRUD:
    """模型配置 CURD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_model_profile(
        self, profile_data: ModelProfileCreate
    ) -> ModelProfile:
        """创建新的模型配置，并返回创建的模型配置实例"""
        new_profile = ModelProfile(**profile_data.model_dump())
        self.session.add(new_profile)
        await self.session.flush()  # 获取新模型配置的 UID
        return new_profile

    async def get_model_profile_by_uid(
        self,
        profile_uid: str,
    ) -> ModelProfile | None:
        """根据模型配置 UID 获取模型配置详情"""
        result = await self.session.execute(
            select(ModelProfile).where(ModelProfile.uid == profile_uid)
        )
        return result.scalars().first()

    async def get_enabled_model_profile_by_uid(
        self,
        profile_uid: str,
    ) -> ModelProfile | None:
        """根据模型配置 UID 获取启用状态的模型配置详情"""
        stmt = select(ModelProfile).where(
            ModelProfile.uid == profile_uid,
            ModelProfile.is_enabled,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
