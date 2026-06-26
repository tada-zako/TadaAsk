from datetime import date, timedelta
from typing import cast

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.crud import ModelProfileCRUD
from app.db.models import Provider
from app.db.schemas import (
    ModelProfileCreate,
    ProviderCreate,
    ProviderCreateWithModels,
    ProviderUpdate,
)
from app.core.security import ProviderAPIKeyCipher


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

    model_config = ConfigDict(extra="ignore")


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

        for provider_id, provider_catalog in catalog:
            if provider_catalog is None:
                continue

            provider_catalog = cast(CatalogProviderData, provider_catalog)
            # 创建 provider 数据
            provider_create = ProviderCreate(
                name=provider_id.lower(),
                base_url=provider_catalog.api,
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

    async def create_or_enable_provider(
        self,
        *,
        provider_data: ProviderCreateWithModels,
        api_key_cipher: ProviderAPIKeyCipher,
    ) -> Provider:
        """
        创建 custom provider，或启用已由模型目录缓存的 provider
        """
        # 处理数据
        provider_name = provider_data.name.strip().lower()
        if not provider_data.api_key:
            # 没有提供 API key，无法启用 provider
            raise ValueError(
                f"Provider '{provider_name}' no API key provided to enable it"
            )

        existing_provider = await self.model_profile_crud.get_provider_by_name(
            name=provider_name
        )
        if existing_provider:
            provider_update_data = ProviderUpdate(
                name=provider_name,
                base_url=provider_data.base_url,
                # 启用 provider，配置 api key
                is_enabled=True,
                api_key=provider_data.api_key,
            )
            provider = await self.model_profile_crud.update_provider(
                provider=existing_provider,
                provider_data=provider_update_data,
                api_key_cipher=api_key_cipher,
            )

        else:
            # 创建用户自定义的 provider
            provider_create_data = provider_data.model_copy(
                update={
                    "name": provider_name,
                    "is_enabled": True,
                    # NOTE: custom provider 一定要设置 is_custom=True
                    "is_custom": True,
                },
            )
            provider = await self.model_profile_crud.create_provider(
                provider_data=provider_create_data,
                api_key_cipher=api_key_cipher,
            )

        if provider_data.model_profiles:
            # 批量 upsert model_profile
            await self.model_profile_crud.bulk_upsert_model_profiles(
                provider=provider,
                profile_data_list=provider_data.model_profiles,
            )

        return provider

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
