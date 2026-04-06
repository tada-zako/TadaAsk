import uuid
from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ======= Document Schemas ======
class DocumentBase(BaseModel):
    filename: str
    source: Literal["local_file", "web_scrape"]


class DocumentCreate(DocumentBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        # 限制使用别名来创建模型实例，预测内部不会实例化该模型
        validate_by_alias=True,
    )


class DocumentRead(DocumentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,  # 允许通过字段名来创建模型实例
    )


# ======= Vector Collection Schemas ======
def generate_collection_name() -> str:
    """pydantic schema 内部函数：生成唯一且符合 ChromaDB 标准的 collection_name"""
    return f"c_{uuid.uuid4().hex[:16]}"


class VectorCollectionBase(BaseModel):
    display_name: str
    # collection_name: str  # 由系统生成，用户不可见


class VectorCollectionCreate(VectorCollectionBase):
    """暴露到 API 中的模型，隐藏 collection_name 字段"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class VectorCollectionInternal(VectorCollectionBase):
    """系统内部使用的模型，包含 collection_name 字段"""

    collection_name: str = Field(default_factory=generate_collection_name)


class VectorCollectionRead(VectorCollectionBase):
    uid: str
    # collection_name: str  # 不返回内部的 collection_name 字段
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Workspace Thread Schemas ======
class WorkspaceThreadBase(BaseModel):
    workspace_thread_name: str
    chat_model: str


class WorkspaceThreadCreate(WorkspaceThreadBase):
    chat_model: str | None = None  # 创建时可选，默认由系统分配

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class WorkspaceThreadRead(WorkspaceThreadBase):
    uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Workspace Chat Schemas ======
class WorkspaceChatBase(BaseModel):
    thread_id: int
    role: Literal["user", "assistant"]
    message: str


class WorkspaceChatInternal(WorkspaceChatBase):
    """系统内部使用的模型，包含 created_at 字段"""

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceChatRead(WorkspaceChatBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )
