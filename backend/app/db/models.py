import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    func,
    String,
    Boolean,
    UniqueConstraint,
    JSON,
    Integer,
    Enum,
    DateTime,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.constants import (
    SourceProcessStatus,
    SourceItemProcessStatus,
    ChatSessionType,
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

    # RAG 相关配置
    visitor_rag_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # visitor 是否启用 RAG
    rag_policy_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # RAG 策略配置

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    site_url: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 项目对应的站点 URL
    description: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # visitor 默认模型配置
    visitor_default_model_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    visitor_default_model_profile: Mapped[Optional["ModelProfile"]] = relationship(
        foreign_keys=[visitor_default_model_profile_id]
    )

    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目下的对话列表

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
    source_type: Mapped[
        str
    ]  # 数据来源类型，如 "file", "web_sitemap", "web_url", "github_repo" 等
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # 公开的来源应用于 visitor 访问

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

    title: Mapped[str]  # 项目标题，如文件名、网页标题等
    filename: Mapped[str]  # 文件名
    storage_key: Mapped[str] = mapped_column(String)  # 存储 key
    origin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 可选 url
    item_hash: Mapped[str]  # 文件或 URL 的哈希值，用于去重和校验

    status: Mapped[SourceItemProcessStatus] = mapped_column(
        Enum(SourceItemProcessStatus), default=SourceItemProcessStatus.PENDING
    )  # 处理状态，如 "pending", "processing", "completed", "failed" 等
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )  # 上次更新或访问时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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
        UniqueConstraint("item_hash", "source_id", name="_item_source_uc"),
    )


class DocumentContent(Base):
    """
    文档内容表：管理知识库中原始文档内容
    """

    __tablename__ = "document_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String)  # 文档的原始文本内容
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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

    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[Optional[str]]  # 模型展示名称，如 "GPT-3.5 Turbo"

    # TODO: 如果没有设置模型的窗口大小，如果配置默认值
    context_window_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=2048)

    supports_stream: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_structured: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    default_params_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 备用参数，设置模型的 top_p, temperature；不一定启用

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # 同一提供商下模型名称唯一
        UniqueConstraint("provider", "model_name", name="_provider_model_uc"),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 外键关联到项目表
    active_model_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )  # 当前对话使用的模型配置
    active_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )  # 当前 session 最新消息的 ID；用于实现对话回退
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )

    active_model_profile: Mapped[Optional["ModelProfile"]] = relationship(
        foreign_keys=[active_model_profile_id]
    )
    active_message: Mapped[Optional["ChatMessage"]] = relationship(
        foreign_keys=[active_message_id],
        post_update=True,  # 解决 ChatSession 和 ChatMessage 之间的循环依赖问题
    )
    project: Mapped["Project"] = relationship(back_populates="chat_sessions")
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

    sequence_index: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 消息在对话中的顺序索引

    role: Mapped[str]
    message: Mapped[str]
    # NOTE: 如果修改 JSON 字典内部的某个值，SQLAlchemy 默认无法检测到这种变化（如果后期需要修改引用，大概率用不到）
    citations_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 引用信息，包含来源、相关文档等元数据
    rag_snapshot_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # RAG 快照信息，包含当时使用的向量、相关文档等元数据

    provider: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 消息生成使用的模型提供商
    model: Mapped[str] = mapped_column(String, nullable=False)  # 消息生成使用的模型名称

    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parent_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )  # 父消息 ID；用于实现对话的回退机制
    chat_session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )  # 外键关联到对话表

    parent_message: Mapped[Optional["ChatMessage"]] = relationship(
        remote_side=[id], foreign_keys=[parent_message_id]
    )  # 自引用关系，建立消息之间的父子关系
    chat_session: Mapped["ChatSession"] = relationship(back_populates="chat_messages")


# TODO: 目前对于实际的业务逻辑还是有些不太清楚：
# 1. 每个 project 对应用户的一个部署的站点
# 2. 每个 project 下可以有多个 source，每个 source 对应一个数据来源（如文件上传、网页爬取等）
# 2.5 这里设置 sources 分层，每个 source 对应一个向量集合，后续可以根据 source 来复用向量集合
# 多 sources 情况下，如何进行向量检索结果的合并和展示？向量查询时，需要一次查询多个向量集合？
# 3. 每个 source 下可以有多个 source_item，每个 source_item 对应一个具体的文件或 URL 等
# 4. 每个 source_item 可以切分成多个 document_chunk，每个 document_chunk 对应向量库中的一个向量
# 4.5 这里的 document_chunk 作用有些困惑：如果目前只是用 SQL 维护一个文档向量 ID 的集合，其实没有多大的作用....
# 这里的期望，其实需要存储 raw_text 和更多的 metadata 字段，实现：
# 4.5.1 在 RAG 检索时，从 SQL 中获取相关文本内容和元数据，向量库只负责存储向量内容 —— 这意味着向量检索逻辑需要单独实现（？到底是否依赖于向量库的检索 API 呢）
# 4.5.2 在后续的文档管理中，实现增量式的文档更新和增删，而不是每次都全量更新向量库
# 4.5.3 提供更加准确的查询方式，不止是通过向量查询，也通过文本内容、元数据等进行查询（？具体的实现方式还不太清楚）
# 4.5.4 能够将检索到的结果，更加清晰的展示给用户，实现文档信息来源的可视化展示功能
# 5. 外来游客通过访问站点，每次对话时，自动创建 ChatSession，并将用户的消息保存到 ChatMessage 中

# TODO: MVP 需要实现的功能：
# - project-source 业务的实现，source-source_item 业务的实现，source_item-chunk 业务的实现
# - project-chat_session 业务组合的实现，这里的重点是需要基于 project 进行 RAG 查询，涉及到多 collection 的查询和结果合并逻辑
