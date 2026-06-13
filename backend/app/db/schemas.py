from typing import Literal, Any
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.constants import (
    SourceProcessStatus,
    SourceItemProcessStatus,
    ChatSessionType,
    SearchMode,
    ChatMessageType,
    ChatMessageRole,
)
from app.utils import generate_collection_name

# =========================
# System Schemas 设计
# =========================


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
    chat_setting: "ProjectChatSettingCreate" = Field(
        default_factory=lambda: ProjectChatSettingCreate(),
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectRead(ProjectBase):
    uid: str
    created_at: datetime

    visitor_default_model_profile: "ModelProfileRead | None" = None

    # TODO: 具体的 chat sessions 传递数据后续完善

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Project Chat Setting Schemas =======
class ProjectChatSettingBase(BaseModel):
    """项目对话设置基类"""

    visitor_default_model_profile_uid: str | None = None
    visitor_rag_enabled: bool = True
    visitor_system_prompt: str | None = None

    # visitor 模型请求参数配置
    visitor_max_output_tokens: int = Field(default=1536, gt=0)
    visitor_temperature: float = Field(default=0.3, ge=0, le=2)
    visitor_top_p: float = Field(default=0.9, gt=0, le=1)
    visitor_timeout: float = Field(default=45.0, gt=0)
    visitor_thinking: bool | Literal["minimal", "low", "medium", "high", "xhigh"] = (
        "low"
    )

    rag_mode: SearchMode = SearchMode.FULL
    rag_top_k: int = Field(default=8, ge=1)

    rag_rerank_enabled: bool = True
    rag_fts_k: int = Field(default=30, ge=0)
    rag_vector_k: int = Field(default=20, ge=0)
    rag_rerank_k: int = Field(default=12, ge=0)

    rag_max_alternative_queries: int = Field(default=2, ge=0, le=10)
    rag_max_keywords: int = Field(default=5, ge=0, le=20)


class ProjectChatSettingCreate(ProjectChatSettingBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProjectChatSettingRead(ProjectChatSettingBase):
    visitor_default_model_profile: "ModelProfileRead | None" = None

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# =========================
# RAG Schemas 设计
# =========================


# ======= Source Schemas =======
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
    filename: str
    storage_key: str
    origin_url: str | None = Field(
        default=None,
        description="Original URL of the document; optional for local files",
    )
    item_hash: str


class SourceItemInternal(SourceItemBase):
    """系统内部使用的模型"""

    ...


class SourceItemInternalWithSourceID(SourceItemInternal):
    """系统内部使用的模型，包含 source_id 字段"""

    source_id: int


class SourceItemRead(SourceItemBase):
    uid: str
    status: SourceItemProcessStatus
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
    filename: str | None = None
    storage_key: str | None = None
    origin_url: str | None = None
    item_hash: str | None = None
    status: SourceItemProcessStatus | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# ======= Document Chunks Schemas =======
class DocumentChunkBase(BaseModel):
    chunk_content: str

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


class DocumentChunkInternal(DocumentChunkBase):
    """系统内部使用的模型"""

    vector_id: str
    chunk_hash: str
    chunk_index: int
    chunk_tokens: str = Field(
        ..., description="Result of FTS tokenization; used for FTS search"
    )
    chunk_pos: int  # 切片在原始文档中的起始位置
    source_item_id: int  # 关联的 SourceItem ID


class DocumentChunkRead(DocumentChunkBase):
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# =========================
# LLM Chat Schemas 设计
# =========================


# ======= Model Profile Schemas =======
class ModelProfileBase(BaseModel):
    provider: str
    model: str

    context_window_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Model context window size in tokens",
    )
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Maximum output tokens allowed for the model",
    )

    supports_stream: bool = True
    supports_structured: bool = True
    is_enabled: bool = True


class ModelProfileCreate(ModelProfileBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ModelProfileRead(ModelProfileBase):
    uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Chat Sessions Schemas =======
class ChatSessionBase(BaseModel):
    title: str
    owner_type: ChatSessionType

    provider: str
    model: str


class ChatSessionInternal(ChatSessionBase):
    project_id: int
    visitor_id: str | None = Field(
        default=None, description="Visitor ID: An optional field for anonymous users"
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


# ======= Chat Message Schemas =======
class ChatMessageBase(BaseModel):
    role: ChatMessageRole
    message: str
    type: ChatMessageType = ChatMessageType.MESSAGE

    sequence: int  # 消息在会话中的顺序
    tail_start_sequence: int | None = (
        None  # 仅在 type=COMPACTION 时使用，表示被压缩对话的起始位置
    )

    provider: str
    model: str

    rag_snapshot: "RAGSnapshot | None" = None


class ChatMessageInternal(ChatMessageBase):
    """系统内部使用的模型，包含 created_at 字段"""

    chat_session_id: int

    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(ChatMessageBase):
    uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= RAG Schemas =======
@dataclass
class HybridSearchResult:
    """混合搜索结果数据结构"""

    chunk_id: int
    vector_id: str
    chunk_index: int
    content: str

    source_id: int
    source_uid: str
    source_name: str

    source_item_id: int
    source_item_uid: str
    title: str
    filename: str
    origin_url: str | None = None

    page_number: int | None = None
    section_header: str | None = None
    metadata: dict[str, Any] | None = None

    rrf_score: float | None = None
    rerank_score: float | None = None


class HybridSearchRequest(BaseModel):
    """混合搜索请求参数"""

    mode: SearchMode = Field(
        default=SearchMode.ADAPTIVE,
        description="Search mode; defaults to 'adaptive'",
    )
    top_k: int = Field(
        default=8,
        ge=1,
        description="Number of top results to return",
    )

    # rerank 策略
    rerank_enabled: bool = Field(
        default=True,
        description="Whether to enable reranking; defaults to True",
    )

    # 召回候选数量
    fts_k: int = Field(
        default=30,
        ge=0,
        description="Number of candidates to retrieve from FTS search",
    )
    vector_k: int = Field(
        default=20,
        ge=0,
        description="Number of candidates to retrieve from vector search",
    )
    rerank_k: int = Field(
        default=12,
        ge=0,
        description="Number of candidates to rerank",
    )

    # expansion 策略
    max_alternative_queries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum number of alternative queries to generate for query expansion",
    )
    max_keywords: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of keywords to extract for query expansion",
    )

    standalone_enabled: bool = False  # 是否执行 standalone 操作


class HybridSearchOptions(HybridSearchRequest):
    """混合搜索选项；包含搜索参数和策略配置"""

    rrf_k: int = 60  # RRF 算法中的参数 K

    # 并发限制
    vector_search_concurrency: int = 6

    # adaptive 判断；判断是否需要进入 FULL 模式
    min_candidates: int = 5  # 最小候选数量；避免检索结果过窄
    min_common_overlap: int = 1  # 最小 FTS & vector 重叠数量；
    min_rerank_overlap: int = 0  # 最小 (FTS & vector) 与 rerank 重叠数量；
    max_hit_score_gap_threshold: float = 0.75  # 最大命中分数阈值；


# ======= RAG Snap Schemas =======
class RAGSnapshotItem(BaseModel):
    """RAG 检索结果快照项"""

    citation_id: int
    source_id: int
    source_item_id: int
    chunk_id: int
    vector_id: str | None = None

    rrf_score: float | None = None
    rerank_score: float | None = None
    used_in_context: bool = True


class RAGSnapshot(BaseModel):
    """RAG 检索结果快照"""

    version: int = 1
    query: str
    standalone_query: str | None = None
    items: list[RAGSnapshotItem] = Field(default_factory=list)
