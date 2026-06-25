import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.constants import (
    ChatMessageRole,
    ChatMessageType,
    ChatSessionType,
    SearchMode,
    SourceItemProcessStatus,
    SourceProcessStatus,
    SourceType,
)


# =========================
# System DDL 设计
# =========================
class Base(AsyncAttrs, DeclarativeBase):
    pass


class Admin(Base):
    """
    admins 表：控制台管理员账号
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)

    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)  # 存储密码哈希值
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 上次登录时间，初始值为 None
    token_version: Mapped[int] = mapped_column(
        Integer, default=0
    )  # token 版本号，用于实现 token 的强制失效，每次密码修改或管理员操作时递增（MVP阶段暂时使用）


class Project(Base):
    """
    项目表：用于管理部署于不同站点的数据
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    project_settings: Mapped["ProjectSettings"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,  # 一对一关系
    )  # 项目的对话设置
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目上下文下的对话列表
    widgets: Mapped[list["ProjectWidget"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目的 widget 部署实例列表

    # 中间表关联
    source_links: Mapped[list["ProjectSourceLink"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目与数据来源的关联列表
    sources: Mapped[list["Source"]] = relationship(
        secondary="project_source_links",
        back_populates="projects",
        viewonly=True,  # 多对多关系只通过 ProjectSourceLink 进行维护
    )  # 项目下的数据来源列表


class ProjectWidget(Base):
    """
    Project widget 部署实例表：一个 Project 可部署到多个站点/widget
    """

    __tablename__ = "project_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    site_origin: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    widget_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # NOTE: 保留字段；widget 配置参数，暂不使用

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project: Mapped["Project"] = relationship(back_populates="widgets")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="_project_widget_name_uc"),
    )


class ProjectSettings(Base):
    """
    项目设置表：存储项目的配置信息，如 RAG 策略等
    """

    __tablename__ = "project_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # RAG 相关配置
    visitor_rag_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # visitor 是否启用 RAG
    visitor_system_prompt: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # visitor 的 system prompt 配置

    # visitor 模型请求参数配置
    visitor_max_output_tokens: Mapped[int] = mapped_column(Integer, default=1536)
    visitor_temperature: Mapped[float] = mapped_column(Float, default=0.3)
    visitor_top_p: Mapped[float] = mapped_column(Float, default=0.9)
    visitor_timeout: Mapped[float] = mapped_column(Float, default=45.0)
    visitor_thinking: Mapped[bool | str] = mapped_column(JSON, default=False)

    # RAG 策略配置
    rag_mode: Mapped[SearchMode] = mapped_column(
        Enum(SearchMode),
        default=SearchMode.FAST,
    )
    rag_top_k: Mapped[int] = mapped_column(Integer, default=8)

    rag_rerank_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rag_fts_k: Mapped[int] = mapped_column(Integer, default=30)
    rag_vector_k: Mapped[int] = mapped_column(Integer, default=20)
    rag_rerank_k: Mapped[int] = mapped_column(Integer, default=12)

    rag_max_alternative_queries: Mapped[int] = mapped_column(Integer, default=2)
    rag_max_keywords: Mapped[int] = mapped_column(Integer, default=5)

    rag_standalone_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    # visitor 默认模型配置
    visitor_default_provider_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    visitor_default_model_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    auxiliary_model_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )  # NOTE: 保留字段；辅助 model 配置，structured_completer 等模型降级

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )  # 一对一关系，外键关联到项目表

    visitor_default_provider: Mapped[Optional["Provider"]] = relationship(
        foreign_keys=[visitor_default_provider_id]
    )
    visitor_default_model_profile: Mapped[Optional["ModelProfile"]] = relationship(
        foreign_keys=[visitor_default_model_profile_id]
    )
    auxiliary_model_profile: Mapped[Optional["ModelProfile"]] = relationship(
        foreign_keys=[auxiliary_model_profile_id]
    )  # NOTE: 保留字段

    project: Mapped["Project"] = relationship(back_populates="project_settings")


# =========================
# RAG DDL 设计
# =========================
class Source(Base):
    """
    数据来源表：管理知识库数据的来源信息
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 对外暴露的标识符
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 数据来源命名

    collection_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 每个数据来源对应一个向量集合，便于复用
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))  # 数据来源类型
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # 公开的来源应用于 visitor 访问

    web_crawl_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Web_Crawl 抓取规则配置

    sync_interval: Mapped[
        int
    ]  # 同步周期，单位为小时，后期添加自动监听同步和定时同步功能时会用到
    status: Mapped[SourceProcessStatus] = mapped_column(
        Enum(SourceProcessStatus), default=SourceProcessStatus.PENDING
    )  # 数据来源状态，如 "pending", "processing", "completed", "failed" 等，后期添加自动监听同步和定时同步功能时会用到
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )  # 上次同步时间，后期添加自动监听同步和定时同步功能时会用到
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- 关系字段 ----
    source_items: Mapped[list["SourceItem"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 数据来源中的具体项目信息，如文件路径、URL 等

    # 中间表关联
    project_links: Mapped[list["ProjectSourceLink"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 数据来源与项目的关联列表
    projects: Mapped[list["Project"]] = relationship(
        secondary="project_source_links",
        back_populates="sources",
        viewonly=True,
    )  # 数据来源对应的项目列表


class ProjectSourceLink(Base):
    """
    项目-数据来源关联表：实现项目与数据来源的多对多关系
    """

    __tablename__ = "project_source_links"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )  # 外键关联到项目表
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )  # 外键关联到数据来源表

    # 反向关系
    project: Mapped["Project"] = relationship(back_populates="source_links")
    source: Mapped["Source"] = relationship(back_populates="project_links")


class SourceItem(Base):
    """
    来源项表：管理每个数据来源中的具体项目信息，如文件路径、URL 等
    """

    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    # 来源项的唯一标识
    # local_file -> storage_key -> file_hash[:2]/file_hash.ext
    # web_crawl -> origin_url
    # github_repo -> repo_url
    item_key: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str]  # 项目标题，如文件名、网页标题等
    filename: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 可选文件名字段
    storage_key: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 存储在对象存储中的文件路径
    origin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 可选 url
    item_hash: Mapped[str]  # 文件或 URL 的哈希值，用于去重和校验

    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 其他元数据信息

    status: Mapped[SourceItemProcessStatus] = mapped_column(
        Enum(SourceItemProcessStatus), default=SourceItemProcessStatus.PENDING
    )  # 处理状态，如 "pending", "processing", "completed", "failed" 等
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )  # 上次更新或访问时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- 关系字段 ----
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE")
    )  # 外键关联到数据来源表

    document_chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="source_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 来源项对应的文档切片列表
    source: Mapped["Source"] = relationship(back_populates="source_items")

    document_content: Mapped[Optional["DocumentContent"]] = relationship(
        back_populates="source_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,  # 一对一关系
    )  # 来源项对应的文档内容

    # 复合唯一约束
    __table_args__ = (
        UniqueConstraint("item_key", "source_id", name="_item_source_uc"),
    )


class DocumentContent(Base):
    """
    文档内容表：管理知识库中原始文档内容
    """

    __tablename__ = "document_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String)  # 文档的原始文本内容

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE")
    )  # 外键关联到来源项表
    source_item: Mapped["SourceItem"] = relationship(back_populates="document_content")


class DocumentChunk(Base):
    """
    文档切片表：管理知识库中切分后的文档信息，每个切片对应一个向量集合中的向量以及其对应的 source_item，
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)

    vector_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )  # 向量 ID，切片的唯一标识 = UUIDv5(NAMESPACE, f"{source_item_id}_{chunk_index}")

    chunk_index: Mapped[int]  # 切片索引：切片在原文档中的排序位置
    chunk_hash: Mapped[str]  # 切片内容的哈希值，用于去重和校验
    chunk_content: Mapped[str]  # 切片的原始文本内容：file_parser 处理后的 markdown 文本
    chunk_tokens: Mapped[str]  # 切片内容的分词结果：提供 FTS 支持
    chunk_pos: Mapped[int]  # 切片在原始文档中的起始位置

    # TODO: 后期来源追溯功能实现预备扩展
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 页码信息，适用于 PDF 等分页文档，其他类型文档可以不使用
    section_header: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 章节标题，适用于有明显章节结构的文档，如 Markdown、HTML 等，其他类型文档可以不使用
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 其他元数据信息，如文档来源、创建时间等，具体内容可以根据实际需求进行调整

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- 关系字段 ----
    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE")
    )  # 外键关联到来源项表
    source_item: Mapped["SourceItem"] = relationship(back_populates="document_chunks")


# TODO: 向量表结构：存储向量化后的结果，目前先不使用
# embedding
# - id
# - chunk_id
# - embedding_model
# - vector_id（对应向量库）


# =========================
# LLM Chat DDL 设计
# =========================
class Provider(Base):
    """
    模型提供商表：管理 LLM 模型提供商配置
    """

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    encrypted_api_key: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 加密后的 API Key
    extra_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # NOTE: 保留字段；配置 header 等，暂不使用

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_custom: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # 是否为自定义 provider

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    model_profiles: Mapped[list["ModelProfile"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ModelProfile(Base):
    """
    模型配置表：管理模型配置信息
    """

    __tablename__ = "model_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    model: Mapped[str] = mapped_column(String, nullable=False)

    # 允许不设置 token 限制，上下文窗口/最大输出由 service 层配置默认值控制
    context_window_tokens: Mapped[Optional[int]]
    max_output_tokens: Mapped[Optional[int]]

    supports_stream: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_structured: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"),
        index=True,
    )  # 外键关联到模型提供商表
    provider: Mapped["Provider"] = relationship(back_populates="model_profiles")

    __table_args__ = (
        # 同一提供商下模型名称唯一
        UniqueConstraint("provider_id", "model", name="_provider_model_uc"),
    )


class ChatSession(Base):
    """
    对话表：管理用户与知识库的对话信息
    """

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    owner_type: Mapped[ChatSessionType] = mapped_column(
        Enum(ChatSessionType)
    )  # 对话拥有者类型

    visitor_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 访客标识，后续可以基于 IP 地址或其他方式生成访客 ID，实现对话的归属和分析
    # TODO: 考虑是否需要记录访客 IP 字段，实现更加细致的访问分析
    title: Mapped[str]
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)

    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0)

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    project: Mapped[Optional["Project"]] = relationship(back_populates="chat_sessions")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 对话中的消息列表


class ChatMessage(Base):
    """
    对话消息表
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 消息在对话中的顺序；从 1 开始递增

    role: Mapped[ChatMessageRole] = mapped_column(Enum(ChatMessageRole))
    message: Mapped[str]
    type: Mapped[ChatMessageType] = mapped_column(
        Enum(ChatMessageType), default=ChatMessageType.MESSAGE
    )
    tail_start_sequence: Mapped[
        Optional[int]
    ]  # ChatMessageType.COMPACTION 类型消息需要记录被压缩对话末尾的开始位置

    # NOTE: 如果修改 JSON 字典内部的某个值，SQLAlchemy 默认无法检测到这种变化（如果后期需要修改引用，大概率用不到）
    rag_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # RAG 快照信息，包含当时使用的向量、相关文档等元数据

    provider: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 消息生成使用的模型提供商
    model: Mapped[str] = mapped_column(String, nullable=False)  # 消息生成使用的模型名称

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- 关系字段 ----
    chat_session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )  # 外键关联到对话表

    chat_session: Mapped["ChatSession"] = relationship(back_populates="chat_messages")

    __table_args__ = (
        UniqueConstraint(
            "chat_session_id",
            "sequence",
            name="_session_sequence_uc",
        ),
    )
