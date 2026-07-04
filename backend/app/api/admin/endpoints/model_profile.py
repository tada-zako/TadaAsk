from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status, Body
from loguru import logger
from sqlalchemy.exc import IntegrityError

from ...deps import APIKeyCipherDeps, ModelProfileCRUDeps, ModelProfileServiceDeps
from app.db.models import ModelProfile, Provider
from app.db.schemas import (
    ModelProfileCreate,
    ModelProfileRead,
    ModelProfileUpdate,
    ProviderCreateWithModels,
    ProviderRead,
    ProviderUpdate,
    ProviderWithModelProfilesRead,
)


router = APIRouter()


async def valid_provider(
    model_profile_crud: ModelProfileCRUDeps,
    provider_uid: Annotated[str, Path(..., description="Provider UID")],
) -> Provider:
    """验证 provider UID 是否有效，返回 provider 实例或抛出 HTTPException。"""
    provider = await model_profile_crud.get_provider_by_uid(provider_uid=provider_uid)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


async def valid_model_profile(
    provider: "ValidProviderDeps",
    model_profile_crud: ModelProfileCRUDeps,
    model_uid: Annotated[str, Path(..., description="Model profile UID")],
) -> ModelProfile:
    """验证 model profile UID 是否属于当前 provider。"""
    model_profile = await model_profile_crud.get_model_profile_by_uid(
        provider_uid=provider.uid,
        model_uid=model_uid,
    )
    if not model_profile:
        raise HTTPException(status_code=404, detail="Model profile not found")
    return model_profile


ValidProviderDeps = Annotated[Provider, Depends(valid_provider)]
ValidModelProfileDeps = Annotated[ModelProfile, Depends(valid_model_profile)]


@router.post("/provider/new", response_model=ProviderWithModelProfilesRead)
async def create_provider(
    payload: Annotated[
        ProviderCreateWithModels,
        Body(..., description="Provider 创建数据"),
    ],
    model_profile_service: ModelProfileServiceDeps,
    api_key_cipher: APIKeyCipherDeps,
):
    """
    创建自定义模型提供商，可同时提交 model_profile。

    目录 provider 由启动同步自动创建，通过 PATCH 接口维护 API key 与启用状态。
    """
    try:
        provider = await model_profile_service.create_custom_provider(
            provider_data=payload,
            api_key_cipher=api_key_cipher,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.warning(f"创建 provider 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider with the same name already exists",
        ) from exc

    return ProviderWithModelProfilesRead.model_validate(provider)


@router.get("/provider/list", response_model=list[ProviderRead])
async def list_providers(
    model_profile_crud: ModelProfileCRUDeps,
):
    """获取提供商列表"""
    providers = await model_profile_crud.list_providers()
    return [ProviderRead.model_validate(provider) for provider in providers]


@router.get("/provider/list/models", response_model=list[ProviderWithModelProfilesRead])
async def list_providers_with_models(
    model_profile_crud: ModelProfileCRUDeps,
):
    """获取提供商列表及其模型配置列表。"""
    providers = await model_profile_crud.list_providers_with_model_profiles()
    return [
        ProviderWithModelProfilesRead.model_validate(provider) for provider in providers
    ]


@router.patch("/provider/{provider_uid}", response_model=ProviderRead)
async def update_provider(
    provider: ValidProviderDeps,
    payload: Annotated[ProviderUpdate, Body(..., description="Provider 更新数据")],
    model_profile_service: ModelProfileServiceDeps,
    api_key_cipher: APIKeyCipherDeps,
):
    """更新模型提供商配置；目录 provider 只允许更新 API key 与启用状态。"""
    try:
        updated_provider = await model_profile_service.update_provider(
            provider=provider,
            provider_data=payload,
            api_key_cipher=api_key_cipher,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.warning(f"更新 provider 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider with the same name already exists",
        ) from exc

    return ProviderRead.model_validate(updated_provider)


@router.delete("/provider/{provider_uid}")
async def delete_provider(
    provider: ValidProviderDeps,
    model_profile_service: ModelProfileServiceDeps,
):
    """删除自定义模型提供商及其模型配置。"""
    try:
        success = await model_profile_service.delete_provider(provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if success:
        return {"uid": provider.uid, "status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete provider")


@router.post(
    "/provider/{provider_uid}/models/new",
    response_model=ModelProfileRead,
)
async def create_model_profile(
    provider: ValidProviderDeps,
    payload: Annotated[ModelProfileCreate, Body(..., description="Model 创建数据")],
    model_profile_service: ModelProfileServiceDeps,
):
    """在自定义 provider 下创建模型配置。"""
    try:
        model_profile = await model_profile_service.create_model_profile(
            provider=provider,
            profile_data=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.warning(f"创建 model profile 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model profile with the same model already exists for this provider",
        ) from exc

    return ModelProfileRead.model_validate(model_profile)


@router.get(
    "/provider/{provider_uid}/models/{model_uid}",
    response_model=ModelProfileRead,
)
async def get_model_profile(
    provider: ValidProviderDeps,
    model_profile: ValidModelProfileDeps,
):
    """获取模型配置详情。"""
    return ModelProfileRead.model_validate(model_profile)


@router.patch(
    "/provider/{provider_uid}/models/{model_uid}",
    response_model=ModelProfileRead,
)
async def update_model_profile(
    provider: ValidProviderDeps,
    model_profile: ValidModelProfileDeps,
    payload: Annotated[ModelProfileUpdate, Body(..., description="Model 配置更新数据")],
    model_profile_service: ModelProfileServiceDeps,
):
    """更新模型配置；目录模型只允许切换 is_enabled。"""
    try:
        updated_profile = await model_profile_service.update_model_profile(
            provider=provider,
            model_profile=model_profile,
            profile_data=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.warning(f"更新 model profile 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model profile with the same model already exists for this provider",
        ) from exc

    return ModelProfileRead.model_validate(updated_profile)


@router.delete("/provider/{provider_uid}/models/{model_uid}")
async def delete_model_profile(
    provider: ValidProviderDeps,
    model_profile: ValidModelProfileDeps,
    model_profile_service: ModelProfileServiceDeps,
):
    """删除自定义 provider 下的模型配置。"""
    try:
        success = await model_profile_service.delete_model_profile(
            provider=provider,
            model_profile=model_profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if success:
        return {"uid": model_profile.uid, "status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete model profile")
