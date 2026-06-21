from typing import Sequence

from sqlalchemy import select, and_, delete, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.db.models import ModelProfile, Provider
from app.db.schemas import (
    ModelProfileInternal,
    ModelProfileCreate,
    ModelProfileUpdate,
    ProviderCreate,
    ProviderUpdate,
    ProviderRead,
    ModelProfileRead,
    ProviderWithModelInternalRead,
)
from app.core.security import ProviderAPIKeyCipher
from app.core.config import settings


class ModelProfileCRUD:
    """模型配置 CURD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ====================
    # Provider 相关操作
    # ====================
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

    async def list_providers(self) -> Sequence[Provider]:
        """获取提供商列表"""
        result = await self.session.execute(
            select(Provider).order_by(Provider.created_at.desc())
        )
        return result.scalars().all()

    async def list_providers_with_model_profiles(self) -> Sequence[Provider]:
        """获取带有模型配置列表的提供商列表"""
        result = await self.session.execute(
            select(Provider)
            .options(selectinload(Provider.model_profiles))
            .order_by(Provider.created_at.desc())
        )
        return result.scalars().all()

    async def get_provider_by_uid(self, provider_uid: str) -> Provider | None:
        """根据提供商 UID 获取提供商详情"""
        result = await self.session.execute(
            select(Provider).where(Provider.uid == provider_uid)
        )
        return result.scalars().first()

    async def get_provider_by_name(self, name: str) -> Provider | None:
        """根据提供商名称获取提供商详情"""
        result = await self.session.execute(
            select(Provider).where(Provider.name == name)
        )
        return result.scalars().first()

    async def get_provider_with_model_profiles_by_uid(
        self, provider_uid: str
    ) -> Provider | None:
        """根据提供商 UID 获取提供商及其模型配置列表"""
        result = await self.session.execute(
            select(Provider)
            .where(Provider.uid == provider_uid)
            .options(selectinload(Provider.model_profiles))
        )
        return result.scalars().first()

    async def update_provider(
        self,
        *,
        provider: Provider,
        provider_data: ProviderUpdate,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """更新模型提供商配置"""
        data = provider_data.model_dump(exclude_unset=True, exclude={"api_key"})
        for key, value in data.items():
            setattr(provider, key, value)

        if "api_key" in provider_data.model_fields_set:
            encrypted_api_key = None
            if provider_data.api_key is not None:
                encrypted_api_key = api_key_cipher.encrypt(
                    provider_data.api_key.get_secret_value()
                )
            provider.encrypted_api_key = encrypted_api_key

        await self.session.flush()
        return provider

    async def delete_provider_by_id(self, provider_id: int) -> bool:
        """根据提供商 ID 删除提供商，返回是否删除成功"""
        result = await self.session.execute(
            select(Provider).where(Provider.id == provider_id)
        )
        provider = result.scalars().first()
        if provider:
            await self.session.delete(provider)
            return True
        return False

    async def delete_disabled_catalog_providers_except(
        self,
        *,
        provider_names: list[str],
    ) -> int:
        """
        清理旧模型目录缓存。

        删除未启用、未配置 API key、且不在当前白名单中的 provider
        """
        if not provider_names:
            return 0

        # 查询需要删除的 provider ID 列表
        stmt = select(Provider.id).where(
            not_(Provider.is_enabled),
            Provider.encrypted_api_key.is_(None),
            Provider.name.not_in(provider_names),
        )
        result = await self.session.execute(stmt)
        provider_ids = result.scalars().all()

        if not provider_ids:
            return 0

        # 批量删除 provider 记录
        # 关联的 model_profile 记录通过级联删除自动清理
        delete_result = await self.session.execute(
            delete(Provider)
            .where(Provider.id.in_(provider_ids))
            .execution_options(synchronize_session="fetch")
        )

        return delete_result.rowcount or 0  # type: ignore

    # ====================
    # ModelProfile 相关操作
    # ====================

    async def create_model_profile(
        self, profile_data: ModelProfileInternal
    ) -> ModelProfile:
        """创建新的模型配置，并返回创建的模型配置实例"""
        new_profile = ModelProfile(**profile_data.model_dump())
        self.session.add(new_profile)
        await self.session.flush()  # 获取新模型配置的 UID
        return new_profile

    async def bulk_upsert_model_profiles(
        self,
        *,
        provider: Provider,
        profile_data_list: list[ModelProfileCreate],
    ) -> None:
        """批量创建或更新 model profile"""
        if not profile_data_list:
            return

        existing_models = await self.session.execute(
            select(ModelProfile).where(ModelProfile.provider_id == provider.id)
        )
        existing_model_by_name = {profile.model: profile for profile in existing_models}
        for model_profile_data in profile_data_list:
            existing_model_profile = existing_model_by_name.get(
                model_profile_data.model
            )

            if existing_model_profile:
                # 已存在同名 model_profile，执行更新操作
                existing_model_profile.context_window_tokens = (
                    model_profile_data.context_window_tokens
                    or existing_model_profile.context_window_tokens
                )
                existing_model_profile.max_output_tokens = (
                    model_profile_data.max_output_tokens
                    or existing_model_profile.max_output_tokens
                )
                existing_model_profile.supports_stream = (
                    model_profile_data.supports_stream
                    if model_profile_data.supports_stream is not None
                    else existing_model_profile.supports_stream
                )
                existing_model_profile.supports_structured = (
                    model_profile_data.supports_structured
                    if model_profile_data.supports_structured is not None
                    else existing_model_profile.supports_structured
                )
                continue

            # 设置默认配置
            if not model_profile_data.context_window_tokens:
                model_profile_data.context_window_tokens = (
                    settings.llm_default_context_window_tokens
                )
            if not model_profile_data.max_output_tokens:
                model_profile_data.max_output_tokens = (
                    settings.llm_default_max_output_tokens
                )

            # 创建关联 model_profile
            provider.model_profiles.append(
                ModelProfile(
                    **model_profile_data.model_dump(),
                )
            )

        await self.session.flush()

    async def list_model_profiles_by_provider_id(
        self, *, provider_id: int
    ) -> Sequence[ModelProfile]:
        """获取指定提供商下的模型配置列表"""
        result = await self.session.execute(
            select(ModelProfile)
            .where(ModelProfile.provider_id == provider_id)
            .order_by(ModelProfile.created_at.desc())
        )
        return result.scalars().all()

    async def get_model_profile_by_model_for_provider(
        self, *, provider_id: int, model: str
    ) -> ModelProfile | None:
        """根据提供商 ID 和模型名称获取模型配置"""
        result = await self.session.execute(
            select(ModelProfile).where(
                ModelProfile.provider_id == provider_id,
                ModelProfile.model == model,
            )
        )
        return result.scalars().first()

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

    async def update_model_profile(
        self,
        *,
        model_profile: ModelProfile,
        profile_data: ModelProfileUpdate,
    ) -> ModelProfile:
        """更新模型配置"""
        for key, value in profile_data.model_dump(exclude_unset=True).items():
            setattr(model_profile, key, value)

        await self.session.flush()
        return model_profile

    async def delete_model_profile_by_id(self, model_profile_id: int) -> bool:
        """根据模型配置 ID 删除模型配置，返回是否删除成功"""
        result = await self.session.execute(
            select(ModelProfile).where(ModelProfile.id == model_profile_id)
        )
        model_profile = result.scalars().first()
        if model_profile:
            await self.session.delete(model_profile)
            return True
        return False

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

    async def get_internal_provider_with_model_profile_by_uid(
        self,
        *,
        provider_uid: str,
        model_uid: str,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> ProviderWithModelInternalRead | None:
        """
        根据提供商 UID 和模型 UID 获取包含提供商信息和模型配置详情的内部使用数据结构；
        包含解密后的 API Key
        """
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
        provider = result.scalars().first()

        if not provider:
            return None

        # 解密 API Key
        decrypted_api_key = None
        if provider.encrypted_api_key:
            decrypted_api_key = api_key_cipher.decrypt(provider.encrypted_api_key)

        # 构建 dict 数据
        provider_dict = ProviderRead.model_validate(provider).model_dump()
        provider_dict["api_key"] = decrypted_api_key
        provider_dict["model_profile"] = ModelProfileRead.model_validate(
            provider.model_profiles[0]
        )

        return ProviderWithModelInternalRead.model_validate(provider_dict)

    async def bulk_upsert_catalog_with_models(
        self,
        *,
        catalog_items: Sequence[tuple[ProviderCreate, Sequence[ModelProfileCreate]]],
    ) -> None:
        """批量同步模型目录中的 provider 及其 model profiles。"""
        if not catalog_items:
            return

        # 一次性加载所有相关 provider，并预加载关联 model_profiles
        provider_names = [provider_data.name for provider_data, _ in catalog_items]
        result = await self.session.execute(
            select(Provider)
            .where(Provider.name.in_(provider_names))
            .options(selectinload(Provider.model_profiles))
        )
        existing_providers_by_name = {
            provider.name: provider for provider in result.scalars().all()
        }

        for provider_data, model_data_list in catalog_items:
            existing_provider = existing_providers_by_name.get(provider_data.name)

            if existing_provider:
                # 更新逻辑
                # 更新 provider 字段
                existing_provider.base_url = provider_data.base_url

                existing_model_profiles_by_name = {
                    model_profile.model: model_profile
                    for model_profile in existing_provider.model_profiles
                }

                # 处理 model_profile
                for model_data in model_data_list:
                    existing_model_profile = existing_model_profiles_by_name.get(
                        model_data.model
                    )

                    if existing_model_profile:
                        # 更新已有模型配置的字段
                        existing_model_profile.context_window_tokens = (
                            model_data.context_window_tokens
                        )
                        existing_model_profile.max_output_tokens = (
                            model_data.max_output_tokens
                        )
                        existing_model_profile.supports_stream = (
                            model_data.supports_stream
                        )
                        existing_model_profile.supports_structured = (
                            model_data.supports_structured
                        )

                    # 创建新模型记录
                    existing_provider.model_profiles.append(
                        ModelProfile(
                            **model_data.model_dump(exclude={"is_enabled"}),
                            is_enabled=False,
                        )
                    )
                    continue

                # 创建新的 provider 及其 model profiles
                provider = Provider(
                    **provider_data.model_dump(exclude={"api_key"}),
                )
                provider.model_profiles = [
                    ModelProfile(
                        **model_data.model_dump(),
                    )
                    for model_data in model_data_list
                ]
                self.session.add(provider)
                continue

        await self.session.flush()
