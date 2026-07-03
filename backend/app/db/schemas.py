from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)
from pydantic.alias_generators import to_camel

from app.core.constants import (
    ChatMessageRole,
    ChatMessageType,
    ChatSessionType,
    CrawlEntryType,
    SearchMode,
    SourceItemProcessStatus,
    SourceProcessStatus,
    SourceType,
)
from app.utils import generate_collection_name, normalize_origin

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


class ProjectCreate(ProjectBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

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


class ProjectWidgetBase(BaseModel):
    name: str
    site_origin: str
    is_enabled: bool = True

    @field_validator("site_origin")
    @classmethod
    def normalize_site_origin(cls, value: str) -> str:
        return normalize_origin(value)


class ProjectWidgetCreate(ProjectWidgetBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectWidgetUpdate(BaseModel):
    name: str | None = None
    site_origin: str | None = None
    is_enabled: bool | None = None

    @field_validator("site_origin")
    @classmethod
    def normalize_site_origin(cls, value: str | None) -> str | None:
        return normalize_origin(value) if value is not None else None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class ProjectWidgetRead(ProjectWidgetBase):
    uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Project Chat Setting Schemas =======
class ProjectSettingsBase(BaseModel):
    """项目对话设置基类"""

    visitor_rag_enabled: bool
    visitor_system_prompt: str | None = None

    # visitor 模型请求参数配置
    visitor_max_output_tokens: int
    visitor_temperature: float
    visitor_top_p: float
    visitor_timeout: float
    visitor_thinking: bool | Literal["minimal", "low", "medium", "high", "xhigh"]

    rag_mode: SearchMode
    rag_top_k: int

    rag_rerank_enabled: bool
    rag_fts_k: int
    rag_vector_k: int
    rag_rerank_k: int

    rag_max_alternative_queries: int
    rag_max_keywords: int

    rag_standalone_enabled: bool


class ProjectSettingsUpdate(BaseModel):
    visitor_rag_enabled: bool | None = None
    visitor_system_prompt: str | None = None

    visitor_max_output_tokens: int | None = None
    visitor_temperature: float | None = None
    visitor_top_p: float | None = None
    visitor_timeout: float | None = None
    visitor_thinking: (
        bool | Literal["minimal", "low", "medium", "high", "xhigh"] | None
    ) = None

    rag_mode: SearchMode | None = None
    rag_top_k: int | None = None

    rag_rerank_enabled: bool | None = None
    rag_fts_k: int | None = None
    rag_vector_k: int | None = None
    rag_rerank_k: int | None = None

    rag_max_alternative_queries: int | None = None
    rag_max_keywords: int | None = None

    rag_standalone_enabled: bool | None = None

    visitor_default_provider_uid: str | None = None
    visitor_default_model_profile_uid: str | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProjectSettingsRead(ProjectSettingsBase):
    visitor_default_provider: "ProviderRead | None" = None
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
    source_type: SourceType
    status: SourceProcessStatus = Field(default=SourceProcessStatus.PENDING)
    sync_interval: int | None = Field(
        default=None,
        ge=1,
        description="Synchronization interval (in hours); optional field for sources that require periodic synchronization, such as web crawl or GitHub repo",
    )
    is_public: bool = Field(
        default=False,
        description="Whether public; if public, the source is accessible to visitors",
    )

    web_crawl_config: "WebCrawlConfig | None" = Field(
        default=None,
        description="Configuration for web crawling; required if source_type is 'web_crawl'",
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
    updated_at: datetime
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
    """Source 更新 schema"""

    source_name: str | None = None
    is_public: bool | None = None
    web_crawl_config: "WebCrawlConfig | None" = Field(
        default=None,
        description="Configuration for web crawling; only accepted by web_crawl sources",
    )

    @field_validator("source_name")
    @classmethod
    def normalize_source_name(cls, value: str | None) -> str | None:
        """确保传入的 source name 不为空"""
        if value is None:
            return None

        value = value.strip()
        if not value:
            raise ValueError("source_name must not be empty")
        return value

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Web Crawl Config Schemas =======
class WebCrawlUrlMatch(BaseModel):
    """Web Crawl URL 匹配规则"""

    exact_urls: list[AnyHttpUrl] = Field(
        default_factory=list, description="List of exact URLs to match"
    )
    path_prefixes: list[str] = Field(
        default_factory=list, description="List of URL path prefixes to match"
    )
    url_patterns: list[str] = Field(
        default_factory=list, description="List of URL patterns (regex) to match"
    )  # NOTE: 保留字段；MVP 阶段不使用
    path_patterns: list[str] = Field(
        default_factory=list, description="List of URL path patterns (regex) to match"
    )  # NOTE: 保留字段；MVP 阶段不使用


class WebCrawlExtractionRule(BaseModel):
    """
    Web Crawl 提取额外规则
    web crawler 除 Config 中的基本规则外，
    更细粒度的提取规则，例如针对特定页面的内容选择器、标题选择器等
    """

    name: str | None = None
    url_match: WebCrawlUrlMatch

    content_selectors: list[str] | None = None
    exclude_selectors: list[str] = Field(
        default_factory=list, description="Appended to global exclude selectors"
    )
    title_selector: str | None = None


class WebCrawlConfig(BaseModel):
    """
    web crawl 抓取规则模型

    example:
    {
        "entryType": "url_list",
        "urls": [
            "https://example.com/",
            "https://example.com/docs/intro",
            "https://example.com/docs/install"
        ],
        "allowedDomains": ["example.com"],

        "contentSelectors": ["main", "article"],
        "excludeSelectors": ["nav", "footer", ".sidebar"],

        "extractionRules": [
            {
            "name": "home page",
            "match": {
                "exactUrls": ["https://example.com/"]
            },
            "contentSelectors": [".homepage-main"],
            "excludeSelectors": [".marketing-banner"]
            },
            {
            "name": "docs pages",
            "match": {
                "pathPrefixes": ["/docs/"]
            },
            "contentSelectors": [".docs-content", "article"],
            "excludeSelectors": [".docs-sidebar", ".toc"]
            }
        ]
    }
    """

    # 抓取类型
    entry_type: CrawlEntryType
    urls: list[AnyHttpUrl] | None = Field(
        default=None,
        description="List of URLs to crawl; required if entry_type is 'url_list'",
    )
    sitemap_url: AnyHttpUrl | None = Field(
        default=None,
        description="Sitemap URL; required if entry_type is 'sitemap'",
    )
    site_root_url: AnyHttpUrl | None = Field(
        default=None,
        description="Site root URL; required if entry_type is 'site_root'",
    )

    # 抓取规则
    allowed_domains: list[str] = Field(default_factory=list)
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)

    content_selectors: list[str] = Field(default_factory=list)
    exclude_selectors: list[str] = Field(default_factory=list)

    # 额外的提取规则集合
    extraction_rules: list[WebCrawlExtractionRule] = Field(
        default_factory=list,
        description="Additional extraction rules for specific pages or sections",
    )

    # 抓取策略
    max_pages: int = Field(
        default=20,
        ge=1,
        description="Maximum number of pages to crawl; optional, used to limit crawl scope",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        description="Maximum crawl depth; optional, used to limit crawl scope",
    )
    request_delay_ms: int = Field(
        default=5000,
        ge=0,
        description="Delay between requests in milliseconds; the default value is 500ms",
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Whether to respect robots.txt rules; the default value is True",
    )


# ======= Source Items Schemas =======
class SourceItemBase(BaseModel):
    item_key: str
    title: str
    filename: str | None = None
    storage_key: str | None = None
    origin_url: str | None = Field(
        default=None,
        description="Original URL of the document; optional for local files",
    )
    item_hash: str
    status: SourceItemProcessStatus = Field(default=SourceItemProcessStatus.PENDING)
    metadata_json: dict[str, Any] | None = None


class SourceItemInternal(SourceItemBase):
    """系统内部使用的模型"""

    ...


class SourceItemInternalWithSourceID(SourceItemInternal):
    """系统内部使用的模型，包含 source_id 字段"""

    source_id: int


class SourceItemRead(SourceItemBase):
    uid: str
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


class SourceItemRenameRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """确保 title 不为空"""
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Document Content Schemas =======
class DocumentContentInternal(BaseModel):
    content: str
    metadata_json: dict[str, Any] | None = None


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


# ======= Provider Schemas =======
class ProviderBase(BaseModel):
    name: str
    base_url: str | None = None

    is_enabled: bool = True
    is_custom: bool = False  # 是否为自定义 provider


class ProviderCreate(ProviderBase):
    api_key: SecretStr | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProviderCreateWithModels(ProviderCreate):
    """包含模型配置的 Provider 创建模型"""

    model_profiles: list["ModelProfileCreate"] = Field(default_factory=list)


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: SecretStr | None = None
    is_enabled: bool | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProviderRead(ProviderBase):
    uid: str

    encrypted_api_key: str | None = Field(
        default=None,
        description="Encrypted API key; the actual API key is not exposed for security reasons",
    )  # NOTE: 安全考虑，前端是否展示 api_key；API Key 解密在前端完成
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


# ======= Model Profile Schemas =======
class ModelProfileBase(BaseModel):
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
        validate_by_name=True,
    )


class ModelProfileInternal(ModelProfileBase):
    """系统内部使用的模型"""

    provider_id: int  # 关联的 Provider ID


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


class ModelProfileUpdate(BaseModel):
    model: str | None = None
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
    supports_stream: bool | None = None
    supports_structured: bool | None = None
    is_enabled: bool | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProviderWithModelInternalRead(ProviderRead):
    """包含模型配置的 Provider 读取模型；内部使用"""

    # 解密后的 API Key；仅内部使用，外部接口不暴露
    api_key: SecretStr | None = None
    model_profile: ModelProfileRead


class ProviderWithModelProfilesRead(ProviderRead):
    """包含模型配置列表的 Provider 读取模型；对外接口使用"""

    model_profiles: list[ModelProfileRead] = Field(default_factory=list)


# ======= Chat Sessions Schemas =======
class ChatSessionBase(BaseModel):
    title: str
    owner_type: ChatSessionType

    provider: str
    model: str


class ChatSessionInternal(ChatSessionBase):
    project_id: int | None = None
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


class ChatMessagesPage(BaseModel):
    """对话消息分页数据结构"""

    messages: list[ChatMessageRead]
    has_more_before: bool
    has_more_after: bool
    oldest_sequence: int | None = None
    newest_sequence: int | None = None

    model_config = ConfigDict(
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

    # citation 基本信息
    citation_id: int
    source_id: int
    source_item_id: int
    chunk_id: int
    vector_id: str | None = None

    # 富快照信息字段
    source_uid: str | None = None
    source_name: str | None = None
    source_item_uid: str | None = None
    title: str | None = None
    filename: str | None = None
    origin_url: str | None = None
    section_header: str | None = None
    page_number: int | None = None
    anchor: str | None = None
    excerpt: str | None = None

    rrf_score: float | None = None
    rerank_score: float | None = None
    used_in_context: bool = True

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class RAGSnapshot(BaseModel):
    """RAG 检索结果快照"""

    version: int = 1
    query: str
    standalone_query: str | None = None
    items: list[RAGSnapshotItem] = Field(default_factory=list)

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )
