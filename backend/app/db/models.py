import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, func, String, UniqueConstraint, JSON, Integer
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


# TODO: 数据库时区配置，确保所有时间字段使用 UTC 存储，并在应用层进行时区转换


class Projects(Base):
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
    description: Mapped[str]
    api_key: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 保留字段，尚不清楚具体配置方式
    site_url: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 项目对应的站点 URL
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chat_sessions: Mapped[list["ChatSessions"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目下的对话列表
    sources: Mapped[list["Sources"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 项目下的数据来源列表


class Sources(Base):
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
    status: Mapped[
        str
    ]  # 数据来源状态，如 "pending", "processing", "completed", "failed" 等，后期添加自动监听同步和定时同步功能时会用到
    # 同步周期
    sync_interval: Mapped[
        int
    ]  # 同步周期，单位为小时，后期添加自动监听同步和定时同步功能时会用到
    last_synced_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )  # 上次同步时间，后期添加自动监听同步和定时同步功能时会用到
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    source_items: Mapped[list["SourceItems"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 数据来源中的具体项目信息，如文件路径、URL 等

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )  # 外键关联到项目表
    project: Mapped["Projects"] = relationship(back_populates="sources")


class SourceItems(Base):
    """
    来源项表：管理每个数据来源中的具体项目信息，如文件路径、URL 等
    """

    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str]  # 项目标题，如文件名、网页标题等
    source_type: Mapped[str]  # 数据来源类型，如 "file", "web_url", "github_repo" 等
    origin_url_or_path: Mapped[str]  # 文件路径或 URL
    item_hash: Mapped[str]  # 文件或 URL 的哈希值，用于去重和校验
    raw_content: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # 原始文本内容，是否使用尚不确定
    version: Mapped[int]  # 版本号，便于实现增量更新和版本管理，现在不确定具体使用方式
    status: Mapped[
        str
    ]  # 处理状态，如 "pending", "processing", "completed", "failed" 等
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )  # 上次更新或访问时间
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE")
    )  # 外键关联到数据来源表

    document_chunks: Mapped[list["DocumentChunks"]] = relationship(
        back_populates="source_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 来源项对应的文档切片列表
    source: Mapped["Sources"] = relationship(back_populates="source_items")

    # 复合唯一约束
    __table_args__ = (
        UniqueConstraint("item_hash", "source_id", name="_item_source_uc"),
    )


class DocumentChunks(Base):
    """
    文档切片表：管理知识库中切分后的文档信息，每个切片对应一个向量集合中的向量以及其对应的 source_item，
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)

    vector_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 向量 ID，切片的唯一标识
    chunk_index: Mapped[int]  # 切片索引，表示该切片在原始文档中的位置
    chunk_hash: Mapped[str]  # 切片内容的哈希值，用于去重和校验
    raw_text: Mapped[str]  # 切片的原始文本内容

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

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE")
    )  # 外键关联到来源项表
    source_item: Mapped["SourceItems"] = relationship(back_populates="document_chunks")


# TODO: 向量表结构：存储向量化后的结果，目前先不使用
# embeddings
# - id
# - chunk_id
# - embedding_model
# - vector_id（对应向量库）


class ChatSessions(Base):
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

    chat_session_name: Mapped[str]
    model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )  # 外键关联到项目表

    project: Mapped["Projects"] = relationship(back_populates="chat_sessions")

    chat_messages: Mapped[list["ChatMessages"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )  # 对话中的消息列表


class ChatMessages(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    role: Mapped[str]
    message: Mapped[str]
    # NOTE: 如果修改 JSON 字典内部的某个值，SQLAlchemy 默认无法检测到这种变化（如果后期需要修改引用，大概率用不到）
    citations: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 引用信息，包含来源、相关文档等元数据  查询没有匹配时允许为空
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chat_session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )  # 外键关联到对话表

    chat_session: Mapped["ChatSessions"] = relationship(back_populates="chat_messages")


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
# 5. 外来游客通过访问站点，每次对话时，自动创建 ChatSession，并将用户的消息保存到 ChatMessages 中

# MVP 需要实现的功能：
# - project-source 业务的实现，source-source_item 业务的实现，source_item-chunk 业务的实现
# - project-chat_session 业务组合的实现，这里的重点是需要基于 project 进行 RAG 查询，涉及到多 collection 的查询和结果合并逻辑
