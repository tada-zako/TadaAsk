import uuid
from typing import Literal, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.config import settings
from app.core.constants import SourceProcessStatus


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
    uid: str
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
    synced_at: datetime
    status: SourceProcessStatus
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceUpdate(BaseModel):
    status: SourceProcessStatus | None = None
    sync_interval: int | None = Field(
        default=None, ge=1, description="同步周期，单位为小时，必须大于等于 1"
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Source Items Schemas ======
class SourceItemBase(BaseModel):
    title: str
    origin_url_or_path: str
    item_hash: str
    raw_content: str | None = None  # 可选字段，存储原始文本内容，便于后续调试和分析
    version: int = Field(default=1, description="文档版本号，默认为 1，每次更新时递增")


class SourceItemRead(SourceItemBase):
    status: SourceProcessStatus
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceItemUpdate(BaseModel):
    title: str | None = None
    version: int | None = Field(
        default=None, ge=1, description="文档版本号，必须大于等于 1，每次更新时递增"
    )
    origin_url_or_path: str | None = None
    raw_content: str | None = None
    item_hash: str | None = None
    status: SourceProcessStatus | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Document Chunks Schemas ======
class DocumentChunkBase(BaseModel):
    vector_id: str
    chunk_index: int
    chunk_hash: str
    raw_text: str  # 切片的原始文本内容，便于后续调试和分析
    source_item_id: int

    page_number: int | None = Field(
        default=None, description="文档页码，针对 PDF 等分页文档可选字段"
    )
    section_header: str | None = Field(
        default=None, description="文档章节标题，便于后续分析和调试"
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None, description="切片的额外元数据信息，便于后续分析和调试"
    )


class DocumentChunkRead(DocumentChunkBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Chat Sessions Schemas ======
class ChatSessionBase(BaseModel):
    chat_session_name: str
    model: str


class ChatSessionCreate(ChatSessionBase):
    model: str = Field(
        default=settings.gemini_model_perf,
        description="对话使用的模型，默认为项目配置的模型",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ChatSessionRead(ChatSessionBase):
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


class ChatMessageCreate(ChatMessageBase):
    chat_session_id: int  # 绑定 ChatSessions 外键


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
