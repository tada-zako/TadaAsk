from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from loguru import logger
from sqlalchemy.exc import IntegrityError

from ...deps import APIKeyCipherDeps, ModelProfileCRUDeps, ModelProfileServiceDeps
from app.db.models import ModelProfile, Provider
from app.db.schemas import (
    ModelProfileCreate,
    ModelProfileInternal,
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
    payload: ProviderCreateWithModels,
    model_profile_service: ModelProfileServiceDeps,
    api_key_cipher: APIKeyCipherDeps,
):
    """
    创建或启用模型提供商。

    已由模型目录缓存的 provider 会更新 API key 并启用；
    custom provider 可同时提交 model_profile。
    """
    try:
        provider = await model_profile_service.create_or_enable_provider(
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


@router.get("/provider/{provider_uid}", response_model=ProviderWithModelProfilesRead)
async def get_provider_with_models(
    provider: ValidProviderDeps,
    model_profile_crud: ModelProfileCRUDeps,
):
    """获取模型提供商详情及其模型配置列表。"""
    provider_with_profiles = (
        await model_profile_crud.get_provider_with_model_profiles_by_uid(
            provider_uid=provider.uid
        )
    )
    return ProviderWithModelProfilesRead.model_validate(
        provider_with_profiles or provider
    )


@router.patch("/provider/{provider_uid}", response_model=ProviderRead)
async def update_provider(
    provider: ValidProviderDeps,
    payload: ProviderUpdate,
    model_profile_crud: ModelProfileCRUDeps,
    api_key_cipher: APIKeyCipherDeps,
):
    """更新模型提供商配置。"""
    if payload.name is not None:
        provider_name = payload.name.strip().lower()
        # 检查是否存在同名 provider
        existing_provider = await model_profile_crud.get_provider_by_name(
            name=provider_name
        )
        if existing_provider and existing_provider.id != provider.id:
            raise HTTPException(
                status_code=400,
                detail="provider with the same name already exists",
            )
        payload = payload.model_copy(update={"name": provider_name})

    try:
        updated_provider = await model_profile_crud.update_provider(
            provider=provider,
            provider_data=payload,
            api_key_cipher=api_key_cipher,
        )
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
    model_profile_crud: ModelProfileCRUDeps,
):
    """删除模型提供商及其模型配置
    NOTE: 暂时不要使用
    """
    success = await model_profile_crud.delete_provider_by_id(provider_id=provider.id)
    if success:
        return {"uid": provider.uid, "status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete provider")


@router.post(
    "/provider/{provider_uid}/models/new",
    response_model=ModelProfileRead,
)
async def create_model_profile(
    provider: ValidProviderDeps,
    payload: ModelProfileCreate,
    model_profile_crud: ModelProfileCRUDeps,
):
    """在指定 provider 下创建模型配置。"""
    existing_model = await model_profile_crud.get_model_profile_by_model_for_provider(
        provider_id=provider.id,
        model=payload.model,
    )
    if existing_model:
        raise HTTPException(
            status_code=400,
            detail="model profile with the same model already exists for this provider",
        )

    profile_data = ModelProfileInternal(
        **payload.model_dump(),
        provider_id=provider.id,
    )
    try:
        model_profile = await model_profile_crud.create_model_profile(profile_data)
    except IntegrityError as exc:
        logger.warning(f"创建 model profile 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model profile with the same model already exists for this provider",
        ) from exc

    return ModelProfileRead.model_validate(model_profile)


@router.get(
    "/provider/{provider_uid}/models",
    response_model=list[ModelProfileRead],
)
async def list_model_profiles(
    provider: ValidProviderDeps,
    model_profile_crud: ModelProfileCRUDeps,
):
    """获取指定 provider 下的模型配置列表。"""
    model_profiles = await model_profile_crud.list_model_profiles_by_provider_id(
        provider_id=provider.id,
    )
    return [ModelProfileRead.model_validate(profile) for profile in model_profiles]


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
    payload: ModelProfileUpdate,
    model_profile_crud: ModelProfileCRUDeps,
):
    """更新模型配置；前端可通过 is_enabled 控制模型是否启用。"""
    if payload.model is not None:
        # 模型名称不允许与同一 provider 下的其他模型配置重复
        existing_model = (
            await model_profile_crud.get_model_profile_by_model_for_provider(
                provider_id=provider.id,
                model=payload.model,
            )
        )
        if existing_model and existing_model.id != model_profile.id:
            raise HTTPException(
                status_code=400,
                detail="model profile with the same model already exists for this provider",
            )

    try:
        updated_profile = await model_profile_crud.update_model_profile(
            model_profile=model_profile,
            profile_data=payload,
        )
    except IntegrityError as exc:
        logger.warning(f"更新 model profile 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model profile with the same model already exists for this provider",
        ) from exc

    return ModelProfileRead.model_validate(updated_profile)


@router.delete("/provider/{provider_uid}/models/{model_uid}")
async def delete_model_profile(
    model_profile: ValidModelProfileDeps,
    model_profile_crud: ModelProfileCRUDeps,
):
    """删除模型配置
    NOTE: 暂时不要使用
    """
    success = await model_profile_crud.delete_model_profile_by_id(
        model_profile_id=model_profile.id
    )
    if success:
        return {"uid": model_profile.uid, "status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete model profile")
