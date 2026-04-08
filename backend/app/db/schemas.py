import uuid
from typing import Literal, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.config import settings


# TODO: 对于 pydantic 模型是否需要设置外键字段，考虑一下...


# ======= Project Schemas ======
class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    api_key: str
    site_url: str


class ProjectCreate(ProjectBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectRead(ProjectBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Source Schemas ======
def generate_collection_name() -> str:
    """pydantic schema 内部函数：生成唯一且符合 ChromaDB 标准的 collection_name"""
    return f"c_{uuid.uuid4().hex[:16]}"


class SourceBase(BaseModel):
    source_name: str
    source_type: Literal["local_file", "web_scrape", "github_repo"]
    status: Literal["pending", "processing", "completed", "failed"]
    sync_interval: int = Field(
        default=24, ge=1, description="同步周期，单位为小时，默认值为 24 小时"
    )


class SourceCreate(SourceBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class SourceInternal(SourceBase):
    """系统内部使用的模型，包含 collection_name 字段"""

    collection_name: str = Field(default_factory=generate_collection_name)


class SourceRead(SourceBase):
    uid: str
    last_synced_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceUpdate(BaseModel):
    status: Literal["pending", "processing", "completed", "failed"] | None = None
    sync_interval: int | None = Field(
        default=None, ge=1, description="同步周期，单位为小时，必须大于等于 1"
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Source Items Schemas ======
class SourceItemBase(BaseModel):
    origin_url_or_path: str
    item_hash: str


class SourceItemCreate(SourceItemBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class SourceItemRead(SourceItemBase):
    last_updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceItemUpdate(BaseModel):
    origin_url_or_path: str | None = None
    item_hash: str | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Document Chunks Schemas ======
class DocumentChunkBase(BaseModel):
    vector_id: str
    source_item_id: int


class DocumentChunkCreate(DocumentChunkBase):
    pass  # 一般由内部创建，不需要外部输入


class DocumentChunkRead(DocumentChunkBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Thread Schemas ======
class ThreadBase(BaseModel):
    thread_name: str
    model: str


class ThreadCreate(ThreadBase):
    model: str = Field(
        default=settings.gemini_model_perf,
        description="对话使用的模型，默认为项目配置的模型",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ThreadRead(ThreadBase):
    uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Chat Message Schemas ======
class ChatMessageBase(BaseModel):
    role: Literal["user", "assistant"]
    message: str
    citations: list[dict[str, Any]] | None = Field(
        default=None, description="消息中的引用列表，每个引用包含相关文档信息等"
    )


class ChatMessageInternal(ChatMessageBase):
    """系统内部使用的模型，包含 created_at 字段"""

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(ChatMessageBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )
