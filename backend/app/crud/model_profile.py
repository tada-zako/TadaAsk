from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.security import ProviderAPIKeyCipher
from app.db.models import ModelProfile, Provider
from app.db.schemas import ModelProfileCreate, ProviderCreate


class ModelProfileCRUD:
    """模型配置 CURD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_provider(
        self,
        *,
        provider_data: ProviderCreate,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """创建新的模型提供商记录"""
        data = provider_data.model_dump(exclude={"api_key"})

        encrypted_api_key = None
        if provider_data.api_key is not None:
            encrypted_api_key = api_key_cipher.encrypt(
                provider_data.api_key.get_secret_value()
            )

        new_provider = Provider(**data, encrypted_api_key=encrypted_api_key)
        self.session.add(new_provider)
        await self.session.flush()  # 获取新提供商的 UID
        return new_provider

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
        provider_uid: str,
        model_uid: str,
    ) -> ModelProfile | None:
        """根据模型配置 UID 获取模型配置详情"""
        result = await self.session.execute(
            select(ModelProfile)
            .join(Provider)
            .where(
                Provider.uid == provider_uid,
                ModelProfile.uid == model_uid,
            )
        )
        return result.scalars().first()

    async def get_enabled_model_profile_by_uid(
        self,
        provider_uid: str,
        model_uid: str,
    ) -> ModelProfile | None:
        """根据模型配置 UID 获取启用状态的模型配置详情"""
        stmt = (
            select(ModelProfile)
            .join(Provider)
            .where(
                Provider.uid == provider_uid,
                ModelProfile.uid == model_uid,
                Provider.is_enabled,
                ModelProfile.is_enabled,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_provider_with_model_profile_by_uid(
        self,
        *,
        provider_uid: str,
        model_uid: str,
    ) -> Provider | None:
        """根据模型配置 UID 获取包含启用状态的模型配置详情的提供商信息"""
        stmt = (
            select(Provider)
            .join(Provider.model_profiles)
            .where(
                and_(
                    Provider.uid == provider_uid,
                    ModelProfile.uid == model_uid,
                    Provider.is_enabled,
                    ModelProfile.is_enabled,
                )
            )
            .options(contains_eager(Provider.model_profiles))
        )

        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()
