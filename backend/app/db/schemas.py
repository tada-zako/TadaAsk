import uuid
from typing import Literal, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.constants import SourceProcessStatus, ChatSessionType


# ======= Admin Schemas =======
class AdminBase(BaseModel):
    username: str


class AdminCreate(AdminBase):
    password_hash: str


class AdminRead(AdminBase):
    uid: str
    created_at: datetime
    last_login_at: datetime | None = None
    token_version: int = Field(
        ...,
        description="Token version number; defaults to 0, increments with each password change",
    )

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class AdminUpdate(BaseModel):
    password_hash: str | None = None
    token_version: int | None = Field(
        default=None,
        description="Token version number; defaults to 0, increments with each password change",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Project Schemas =======
class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    site_url: str


class ProjectCreate(ProjectBase):
    provider: str | None = Field(
        default=None,
        description="Model Provider; can be left empty during initial creation",
    )
    model: str | None = Field(
        default=None,
        description="Model Name; can be left empty during initial creation",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectRead(ProjectBase):
    uid: str
    created_at: datetime
    provider: str
    model: str

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Source Schemas =======
def generate_collection_name() -> str:
    """pydantic schema 内部函数：生成唯一且符合 ChromaDB 标准的 collection_name"""
    return f"c_{uuid.uuid4().hex[:16]}"


class SourceBase(BaseModel):
    source_name: str
    source_type: Literal["local_file", "web_scrape", "github_repo"]
    sync_interval: int = Field(
        default=24,
        ge=1,
        description="Synchronization interval (in hours); the default value is 24",
    )
    is_public: bool = Field(
        default=False,
        description="Whether public; if public, the source is accessible to visitors",
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


class SourceWithItemsCount(SourceRead):
    items_count: int = Field(
        default=0, description="Number of documents associated with the source"
    )


class SourceUpdate(BaseModel):
    status: SourceProcessStatus | None = None
    sync_interval: int | None = Field(
        default=None, ge=1, description="Synchronization interval (in hours)"
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Source Items Schemas =======
class SourceItemBase(BaseModel):
    title: str
    local_path: str
    origin_url: str | None = Field(
        default=None,
        description="Original URL of the document; optional for local files",
    )
    item_hash: str


class SourceItemInternal(SourceItemBase):
    """系统内部使用的模型，包含 source_id 字段"""

    source_id: int


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
    local_path: str | None = None
    origin_url: str | None = None
    item_hash: str | None = None
    status: SourceProcessStatus | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Document Chunks Schemas =======
class DocumentChunkBase(BaseModel):
    vector_id: str
    chunk_index: int
    chunk_hash: str
    chunk_pos: int  # 切片在原始文档中的起始位置
    source_item_id: int

    page_number: int | None = Field(
        default=None,
        description="Document page number (Optional field for pageinated documents such as PDFs)",
    )
    section_header: str | None = Field(
        default=None,
        description="Document section header (Optional field)",
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None, description="Additional metadata"
    )


class DocumentChunkRead(DocumentChunkBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Chat Sessions Schemas =======
class ChatSessionBase(BaseModel):
    chat_session_name: str
    model: str


class ChatSessionInternal(ChatSessionBase):
    visitor_id: str | None = Field(
        default=None, description="Visitor ID: An optional field for anonymous users"
    )
    session_type: ChatSessionType
    project_id: int = Field(..., description="Associated project ID")


class ChatSessionRead(ChatSessionBase):
    uid: str
    session_type: ChatSessionType
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Chat Message Schemas =======
class ChatMessageBase(BaseModel):
    role: Literal["user", "assistant"]
    message: str


class ChatMessageInternal(ChatMessageBase):
    """系统内部使用的模型，包含 created_at 字段"""

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(ChatMessageBase):
    citations: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of citations associated with the message, if any",
    )
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )
