from datetime import date, timedelta
from typing import cast

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.crud import ModelProfileCRUD
from app.db.models import ModelProfile, Provider
from app.db.schemas import (
    ModelProfileCreate,
    ModelProfileInternal,
    ModelProfileUpdate,
    ProviderCreate,
    ProviderCreateWithModels,
    ProviderUpdate,
)
from app.core.security import ProviderAPIKeyCipher
from app.providers.official import OFFICIAL_PROVIDERS


# 保留最近一段时间内发布的模型，避免启动时缓存过多历史型号。
CATALOG_MODEL_MAX_AGE_DAYS = 540

# 过滤非对话模型；过滤关键词。
NON_CHAT_FAMILY_PARTS = (
    "audio",
    "embedding",
    "image",
    "moderation",
    "rerank",
    "speech",
    "transcribe",
    "tts",
    "vision",
)


class CatalogModelLimit(BaseModel):
    context: int | None = None
    output: int | None = None

    model_config = ConfigDict(extra="ignore")


class CatalogModelData(BaseModel):
    """目录中的模型数据结构。"""

    id: str | None = None
    name: str | None = None
    family: str | None = None
    release_date: date | None = None
    tool_call: bool | None = None
    modalities: dict[str, list[str]] | None = None
    limit: CatalogModelLimit | None = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("release_date", mode="before")
    @classmethod
    def normalize_release_date(cls, value: object) -> date | None:
        """release_date 字段验证器；
        str 类型转换成 date 类型，或无效格式转换成 None。"""
        if value is None or isinstance(value, date):
            return value
        if not isinstance(value, str):
            return None

        raw_value = value.strip()
        if not raw_value:
            return None
        if len(raw_value) == 7:
            # 补全字段；"2023-11" -> "2023-11-01"
            raw_value = f"{raw_value}-01"

        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            return None


class CatalogProviderData(BaseModel):
    """目录中的 provider 数据结构。"""

    id: str | None = None
    name: str | None = None
    api: str | None = None
    env: list[str] | None = None
    models: dict[str, CatalogModelData] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class TargetCatalog(BaseModel):
    openai: CatalogProviderData | None = None
    google: CatalogProviderData | None = None
    anthropic: CatalogProviderData | None = None
    alibaba: CatalogProviderData | None = None
    deepseek: CatalogProviderData | None = None
    minimax: CatalogProviderData | None = None
    minimax_cn: CatalogProviderData | None = Field(default=None, alias="minimax-cn")
    moonshotai: CatalogProviderData | None = None
    groq: CatalogProviderData | None = None
    zhipuai: CatalogProviderData | None = None
    alibaba_cn: CatalogProviderData | None = Field(default=None, alias="alibaba-cn")

    model_config = ConfigDict(extra="ignore")

    def get(self, provider_name: str) -> CatalogProviderData | None:
        """按 models.dev 的原始 Provider ID 读取目录项。"""
        field_name = provider_name.replace("-", "_")
        return getattr(self, field_name, None)


class ModelProfileService:
    """模型提供商与模型配置编排服务。"""

    def __init__(self, *, model_profile_crud: ModelProfileCRUD):
        self.model_profile_crud = model_profile_crud

    async def sync_model_catalog(self, *, models_url: str) -> None:
        """拉取模型目录并缓存到本地数据库。"""
        try:
            catalog = await self._fetch_model_catalog(models_url=models_url)
        except Exception as exc:
            logger.warning(f"拉取模型目录失败，跳过本次同步：{exc}")
            return

        # provider 与 model_profile 的批量更新数据
        catalog_items: list[tuple[ProviderCreate, list[ModelProfileCreate]]] = []

        for provider_definition in OFFICIAL_PROVIDERS:
            provider_catalog = catalog.get(provider_definition.catalog_name)
            if provider_catalog is None:
                continue

            provider_catalog = cast(CatalogProviderData, provider_catalog)
            # 创建 provider 数据
            provider_create = ProviderCreate(
                name=provider_definition.name,
                base_url=provider_definition.base_url,
                is_enabled=False,
                is_custom=False,  # 模型目录同步的 provider，默认不是自定义 provider
            )

            # 筛选模型并创建 model_profile 数据
            model_creates = [
                ModelProfileCreate(
                    model=model_id,
                    context_window_tokens=self._positive_limit_or_none(
                        model_data.limit.context if model_data.limit else None
                    ),
                    max_output_tokens=self._positive_limit_or_none(
                        model_data.limit.output if model_data.limit else None
                    ),
                    supports_stream=True,
                    supports_structured=(
                        model_data.tool_call
                        if model_data.tool_call is not None
                        else True
                    ),
                    is_enabled=False,
                )
                for model_id, model_data in self._select_recent_chat_models(
                    provider_catalog.models
                )
            ]

            catalog_items.append((provider_create, model_creates))

        if not catalog_items:
            logger.warning("模型目录中没有可同步的目标 provider，跳过本次同步")
            return

        # 一并对 provider-model 进行写库操作
        await self.model_profile_crud.bulk_upsert_catalog_with_models(
            catalog_items=catalog_items,
        )

        # 清理过期的 provider
        deleted_count = (
            await self.model_profile_crud.delete_disabled_catalog_providers_except(
                provider_names=[provider.name for provider, _ in catalog_items],
            )
        )
        logger.info(
            "模型目录同步完成："
            f"providers={len(catalog_items)}, "
            f"cleaned_providers={deleted_count}"
        )

    async def create_custom_provider(
        self,
        *,
        provider_data: ProviderCreateWithModels,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """创建用户自定义 provider，可同时创建其下模型配置。"""
        provider_name = self._normalize_provider_name(provider_data.name)

        existing_provider = await self.model_profile_crud.get_provider_by_name(
            name=provider_name
        )
        if existing_provider:
            raise ValueError("provider with the same name already exists")

        if provider_data.is_enabled:
            self._validate_custom_provider_can_be_enabled(
                api_key=self._has_api_key_value(provider_data.api_key),
                base_url=provider_data.base_url,
            )

        provider_create_data = ProviderCreate(
            name=provider_name,
            base_url=provider_data.base_url,
            api_key=provider_data.api_key,
            is_enabled=provider_data.is_enabled,
            is_custom=True,
        )
        provider = await self.model_profile_crud.create_provider(
            provider_data=provider_create_data,
            api_key_cipher=api_key_cipher,
        )

        if provider_data.model_profiles:
            # 自定义 provider 才允许用户维护 model_profile。
            await self.model_profile_crud.bulk_upsert_model_profiles(
                provider=provider,
                profile_data_list=provider_data.model_profiles,
            )

        # ProviderWithModelProfilesRead 会读取 model_profiles，返回前显式预加载关系。
        provider_with_models = (
            await self.model_profile_crud.get_provider_with_model_profiles_by_uid(
                provider.uid
            )
        )
        return provider_with_models or provider

    async def update_provider(
        self,
        *,
        provider: Provider,
        provider_data: ProviderUpdate,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """按 provider 来源更新配置。"""
        self._validate_provider_update_nulls(provider_data)
        if provider.is_custom:
            # 更新自定义 provider 配置
            return await self._update_custom_provider(
                provider=provider,
                provider_data=provider_data,
                api_key_cipher=api_key_cipher,
            )
        return await self._update_catalog_provider(
            provider=provider,
            provider_data=provider_data,
            api_key_cipher=api_key_cipher,
        )

    async def delete_provider(self, *, provider: Provider) -> bool:
        """仅允许删除用户自定义 provider。"""
        if not provider.is_custom:
            raise ValueError("catalog provider cannot be deleted; disable it instead")
        return await self.model_profile_crud.delete_provider_by_id(
            provider_id=provider.id
        )

    async def create_model_profile(
        self,
        *,
        provider: Provider,
        profile_data: ModelProfileCreate,
    ) -> ModelProfile:
        """仅允许在自定义 provider 下创建模型配置。"""
        if not provider.is_custom:
            raise ValueError("catalog provider models cannot be created manually")

        existing_model = (
            await self.model_profile_crud.get_model_profile_by_model_for_provider(
                provider_id=provider.id,
                model=profile_data.model,
            )
        )
        # 存在同名 model
        if existing_model:
            raise ValueError(
                "model profile with the same model already exists for this provider"
            )

        internal_data = ModelProfileInternal(
            **profile_data.model_dump(),
            provider_id=provider.id,
        )
        return await self.model_profile_crud.create_model_profile(internal_data)

    async def update_model_profile(
        self,
        *,
        provider: Provider,
        model_profile: ModelProfile,
        profile_data: ModelProfileUpdate,
    ) -> ModelProfile:
        """按 provider 来源更新模型配置。"""
        self._validate_model_profile_update_nulls(profile_data)
        if not provider.is_custom:
            # 后端初始化模型更新
            return await self._update_catalog_model_profile(
                model_profile=model_profile,
                profile_data=profile_data,
            )

        if profile_data.model is not None:
            existing_model = (
                await self.model_profile_crud.get_model_profile_by_model_for_provider(
                    provider_id=provider.id,
                    model=profile_data.model,
                )
            )
            if existing_model and existing_model.id != model_profile.id:
                # 重复创建同名 model 记录
                raise ValueError(
                    "model profile with the same model already exists for this provider"
                )

        return await self.model_profile_crud.update_model_profile(
            model_profile=model_profile,
            profile_data=profile_data,
        )

    async def delete_model_profile(
        self,
        *,
        provider: Provider,
        model_profile: ModelProfile,
    ) -> bool:
        """仅允许删除用户自定义 provider 下的模型配置。"""
        if not provider.is_custom:
            raise ValueError("catalog provider models cannot be deleted")
        return await self.model_profile_crud.delete_model_profile_by_id(
            model_profile_id=model_profile.id
        )

    async def _fetch_model_catalog(self, *, models_url: str) -> TargetCatalog:
        """拉取并解析目标模型目录。"""
        headers = {"User-Agent": "TadaAsk/0.1"}
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            response = await client.get(models_url)
            response.raise_for_status()

        return TargetCatalog.model_validate_json(response.content)

    def _select_recent_chat_models(
        self,
        models: dict[str, CatalogModelData],
    ) -> list[tuple[str, CatalogModelData]]:
        """筛选模型
        筛选策略：
        - 发布日期在 release_after 之后；
        - 具有对话能力（非 embedding、audio、image 等模型）
        """
        release_after = date(2026, 6, 1) - timedelta(days=CATALOG_MODEL_MAX_AGE_DAYS)
        selected_models: list[tuple[str, CatalogModelData]] = []

        for model_id, model_data in models.items():
            if model_data.release_date is None:
                # 跳过没有发布日期的模型
                continue
            if model_data.release_date < release_after:
                # 跳过发布日期过旧的模型
                continue
            if not self._is_chat_model(model_data):
                # 跳过非对话模型
                continue
            selected_models.append((model_id, model_data))
        # 按照发布日期降序排序
        return sorted(
            selected_models,
            key=lambda item: (item[1].release_date, item[0]),
            reverse=True,
        )

    def _is_chat_model(self, model_data: CatalogModelData) -> bool:
        """判断模型是否具有对话能力"""
        family = str(model_data.family or "").lower()
        if any(part in family for part in NON_CHAT_FAMILY_PARTS):
            # family 字段包含非对话模型关键词
            return False

        output_modalities = (model_data.modalities or {}).get("output")
        if output_modalities and "text" not in output_modalities:
            # 输出模态不包含 text
            return False

        return True

    def _positive_limit_or_none(self, value: int | None) -> int | None:
        """目录中 0 表示未知，本地模型配置用 None 表达未知。"""
        if value is None or value <= 0:
            return None
        return value

    async def _update_catalog_provider(
        self,
        *,
        provider: Provider,
        provider_data: ProviderUpdate,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """目录 provider 只允许维护启用状态和 API key。"""
        forbidden_fields = provider_data.model_fields_set & {"name", "base_url"}
        if forbidden_fields:
            # 不允许设置 name, base_url 字段
            raise ValueError("catalog provider only allows api_key and is_enabled")

        self._validate_catalog_provider_can_be_enabled(
            provider=provider,
            provider_data=provider_data,
        )
        # 执行写库
        return await self.model_profile_crud.update_provider(
            provider=provider,
            provider_data=provider_data,
            api_key_cipher=api_key_cipher,
        )

    async def _update_custom_provider(
        self,
        *,
        provider: Provider,
        provider_data: ProviderUpdate,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """自定义 provider 允许维护基础配置。"""
        if provider_data.name is not None:
            provider_name = self._normalize_provider_name(provider_data.name)
            existing_provider = await self.model_profile_crud.get_provider_by_name(
                name=provider_name
            )
            if existing_provider and existing_provider.id != provider.id:
                raise ValueError("provider with the same name already exists")
            provider_data = provider_data.model_copy(update={"name": provider_name})

        self._validate_custom_provider_can_be_enabled(
            # 如果前端没有传递，则使用更新前的已有记录
            api_key=((provider_data.api_key or provider.encrypted_api_key) is not None),
            base_url=(provider_data.base_url or provider.base_url),
            is_enabled=(provider_data.is_enabled or provider.is_enabled),
        )
        # 执行写库
        return await self.model_profile_crud.update_provider(
            provider=provider,
            provider_data=provider_data,
            api_key_cipher=api_key_cipher,
        )

    async def _update_catalog_model_profile(
        self,
        *,
        model_profile: ModelProfile,
        profile_data: ModelProfileUpdate,
    ) -> ModelProfile:
        """目录模型只允许切换启用状态。"""
        if profile_data.model_fields_set - {"is_enabled"}:
            # 不允许设置除了 is_enabled 之外的字段
            raise ValueError("catalog model only allows is_enabled")

        if "is_enabled" not in profile_data.model_fields_set:
            # 无意义
            return model_profile
        return await self.model_profile_crud.update_model_profile(
            model_profile=model_profile,
            profile_data=ModelProfileUpdate(is_enabled=profile_data.is_enabled),
        )

    def _normalize_provider_name(self, name: str) -> str:
        """统一 provider 名称，避免大小写重复。"""
        provider_name = name.strip().lower()
        if not provider_name:
            raise ValueError("provider name cannot be empty")
        return provider_name

    def _validate_provider_update_nulls(self, provider_data: ProviderUpdate) -> None:
        """禁止把非空字段显式更新为 null。"""
        if (
            "api_key" in provider_data.model_fields_set
            and self._has_api_key_value(provider_data.api_key) is None
        ):
            raise ValueError("API key cannot be empty")
        if (
            "is_enabled" in provider_data.model_fields_set
            and provider_data.is_enabled is None
        ):
            raise ValueError("is_enabled cannot be null")
        if "name" in provider_data.model_fields_set and provider_data.name is None:
            raise ValueError("provider name cannot be null")

    def _validate_model_profile_update_nulls(
        self, profile_data: ModelProfileUpdate
    ) -> None:
        """禁止把 model 与启用状态显式更新为 null。"""
        if "model" in profile_data.model_fields_set and profile_data.model is None:
            raise ValueError("model cannot be null")
        if (
            "is_enabled" in profile_data.model_fields_set
            and profile_data.is_enabled is None
        ):
            raise ValueError("is_enabled cannot be null")

    def _validate_catalog_provider_can_be_enabled(
        self,
        *,
        provider: Provider,
        provider_data: ProviderUpdate,
    ) -> None:
        """目录 provider 启用时必须已经有或同时提交 API key。"""
        if provider.name == "ollama":
            return
        if provider.encrypted_api_key is None and provider_data.api_key is None:
            raise ValueError("API key is required to enable this provider")

    def _has_api_key_value(self, api_key: SecretStr | None) -> bool:
        """检查 API key 是否真正有内容。"""
        if api_key is None:
            return False
        return bool(api_key.get_secret_value().strip())

    def _validate_custom_provider_can_be_enabled(
        self,
        *,
        api_key: bool,
        base_url: str | None,
        is_enabled: bool = True,
    ) -> None:
        """自定义 provider 启用时必须满足运行时调用所需配置。"""
        if not is_enabled:
            return
        if not api_key:
            raise ValueError("API key is required to enable custom provider")
        if not base_url or not base_url.strip():
            raise ValueError("Base URL is required to enable custom provider")
