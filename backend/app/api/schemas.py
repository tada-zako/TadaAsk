from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

from app.core.constants import SourceItemProcessStatus, IngestStage, RAGIngestEventType
from app.db.schemas import HybridSearchResult, HybridSearchRequest
from app.services import SearchDebugInfo


class AdminChatRequest(BaseModel):
    """Admin chat 请求结构体"""

    message: str = Field(..., description="用户输入的消息文本")
    chat_session_uid: str | None = None
    model_profile_uid: str

    rag_enabled: bool = True
    source_uids: list[str] | None = None  # 可选的文档来源过滤条件
    rag_options: HybridSearchRequest | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class VisitorChatRequest(BaseModel):
    """Visitor chat 请求结构体"""

    message: str = Field(..., description="用户输入的消息文本")
    chat_session_uid: str | None = None

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


class IngestProgressEvent(BaseModel):
    """文档处理进度实事件：SSE data 部分结构"""

    event: RAGIngestEventType
    source_uid: str
    source_item_uid: str | None = None
    ingest_stage: IngestStage
    process_status: SourceItemProcessStatus
    item_progress: float | None = None  # 当前文档处理进度，0.0 - 1.0
    message: str | None = None  # 可选的进度描述信息
    error: str | None = None  # 可选的错误信息，仅在 process_status=FAILED 时提供

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


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


class HybridSearchResponse(BaseModel):
    """混合搜索响应结构体"""

    raw_query: str
    results: list[HybridSearchResult] = Field(default_factory=list)
    debug_info: SearchDebugInfo | None = None
