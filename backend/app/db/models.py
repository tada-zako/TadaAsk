import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, func, String, UniqueConstraint, JSON
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

    threads: Mapped[list["Threads"]] = relationship(
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
    project: Mapped["Projects"] = relationship(back_populates="threads")


class SourceItems(Base):
    """
    来源项表：管理每个数据来源中的具体项目信息，如文件路径、URL 等
    """

    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    origin_url_or_path: Mapped[str]  # 文件路径或 URL
    item_hash: Mapped[str]  # 文件或 URL 的哈希值，用于去重和校验
    last_updated_at: Mapped[datetime] = mapped_column(
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
    目前只作为 SQL 和向量 chunk 的映射，不负责 text 的存储
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)

    vector_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 向量 ID，唯一标识一个切片
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("source_items.id", ondelete="CASCADE")
    )  # 外键关联到来源项表
    source_item: Mapped["SourceItems"] = relationship(back_populates="document_chunks")


class Threads(Base):
    """
    对话表：管理用户与知识库的对话信息
    """

    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True)

    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    thread_name: Mapped[str]
    model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )  # 外键关联到项目表

    project: Mapped["Projects"] = relationship(back_populates="threads")

    chat_messages: Mapped[list["ChatMessages"]] = relationship(
        back_populates="thread",
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

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE")
    )  # 外键关联到对话表

    thread: Mapped["Threads"] = relationship(back_populates="chat_messages")
