from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

from app.providers import ThinkingLevel
from app.core.constants import (
    SourceItemProcessStatus,
    IngestStage,
    RAGSyncEventType,
    SourceProcessStatus,
    RAGJobStatus,
    RAGJobType,
)
from app.db.schemas import HybridSearchResult, HybridSearchRequest, SourceItemRead
from app.services import SearchDebugInfo


class AdminChatRequest(BaseModel):
    """Admin chat 请求结构体"""

    # LLM Chat 请求的基础字段
    message: str = Field(..., description="用户输入的消息文本")
    chat_session_uid: str | None = None
    provider_uid: str
    model_uid: str
    admin_system_prompt: str | None = Field(
        default=None,
        description="Admin 侧请求级附加 system prompt；为空时使用默认系统提示词",
    )

    # LLM 请求参数配置
    temperature: float | None = None
    top_p: float | None = None
    thinking: ThinkingLevel = Field(
        default="medium", description="LLM 思考等级配置；False 为 none 或 minimal"
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class AdminRAGChatRequest(AdminChatRequest):
    """Admin RAG Chat 请求结构体；包含 RAG 相关的参数配置"""

    # RAG 相关参数配置
    source_uids: list[str] = Field(
        default_factory=list,
        description="RAG 检索使用的 source_uids 列表；project-scoped chat 中表示额外 sources",
    )
    rag_options: HybridSearchRequest = Field(default_factory=HybridSearchRequest)


class VisitorChatRequest(BaseModel):
    """Visitor chat 请求结构体"""

    message: str = Field(..., description="用户输入的消息文本")
    chat_session_uid: str | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class AdminChatCancelResponse(BaseModel):
    """Admin chat cancel 响应结构体"""

    session_uid: str
    generation_uid: str
    cancelled: bool = Field(
        default=False,
        description="是否成功取消 LLM 生成",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class VisitorChatCancelResponse(BaseModel):
    """Visitor chat cancel 响应结构体"""

    widget_uid: str
    generation_uid: str
    cancelled: bool = Field(
        default=False,
        description="是否成功取消 LLM 生成",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class AdminChatRevertResponse(BaseModel):
    """Admin chat revert 响应结构体"""

    session_uid: str
    message_uid: str
    target_sequence: int
    deleted_count: int

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceItemDeleteResponse(BaseModel):
    """Source item 删除响应结构体"""

    source_uid: str
    source_item_uid: str
    deleted_vector_count: int
    file_deleted: bool

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class SourceDeleteResponse(BaseModel):
    """Source 删除响应结构体"""

    source_uid: str
    status: str = "deleted"
    deleted_source_item_count: int
    file_deleted_count: int
    file_delete_failed_count: int
    vector_collection_deleted: bool
    cleanup_errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ModelSelection(BaseModel):
    """模型选择请求结构体"""

    model_profile_uid: str | None = Field(
        default=None,
        description="模型配置 UID",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


# class AgentRequest(ChatRequest):
#     # 额外字段，指定 Agent 运行支持的功能
#     mode: Literal["rag_search", "web_search"] = Field(
#         default="rag_search",
#         description="Agent 运行模式，决定使用哪个工具集，目前支持 'rag_search' 和 'web_search'",
#     )


class Token(BaseModel):
    """JWT 访问令牌响应模型"""

    access_token: str
    token_type: str = Field(default="bearer")


class TokenData(BaseModel):
    """JWT 令牌数据模型，用于解析令牌中的有效载荷"""

    username: str = Field(..., description="管理员用户名")
    token_version: int = Field(..., description="Token 版本号")


class IngestPausedResponse(BaseModel):
    """文档处理暂停响应结构"""

    source_uid: str
    source_item_uid: str
    process_status: SourceItemProcessStatus
    message: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class RAGSyncCounters(BaseModel):
    """RAG sync 过程中的计数器"""

    discovered: int = 0
    fetched: int = 0
    skipped: int = 0
    upserted: int = 0
    indexed: int = 0
    completed: int = 0
    paused: int = 0
    failed: int = 0
    pruned: int = 0
    cleanup_failed: int = 0


class RAGSyncEvent(BaseModel):
    """RAG sync/ingest SSE 事件结构体"""

    event: RAGSyncEventType

    source_uid: str
    source_status: SourceProcessStatus | None = None

    source_item_uid: str | None = None
    source_item_status: SourceItemProcessStatus | None = None
    source_item: SourceItemRead | None = (
        None  # 传递 source_item 详细信息，便于前端动态更新 source_item list
    )

    ingest_stage: IngestStage | None = None
    item_progress: float | None = None
    sync_progress: float | None = None

    counters: RAGSyncCounters | None = None

    message: str | None = None
    error: str | None = None
    error_id: str | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class RAGJobStartResponse(BaseModel):
    """RAG 后台任务启动响应结构体"""

    job_uid: str
    job_type: RAGJobType
    source_uid: str
    source_item_uids: list[str] = Field(default_factory=list)
    status: RAGJobStatus

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class RAGJobRead(RAGJobStartResponse):
    """RAG 后台任务读取结构体"""

    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class ActiveRAGJobsResponse(BaseModel):
    """当前运行中的 RAG 后台任务列表。"""

    jobs: list[RAGJobRead] = Field(default_factory=list)

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
    )


class HybridSearchResponse(BaseModel):
    """混合搜索响应结构体"""

    raw_query: str
    results: list[HybridSearchResult] = Field(default_factory=list)
    debug_info: SearchDebugInfo | None = None
