from datetime import datetime
import uuid

from sqlalchemy import ForeignKey, func, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Documents(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str]  # 允许重复
    source: Mapped[str]
    file_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "file_hash", "vector_collection_id", name="_file_collection_uc"
        ),
    )

    vector_collection_id: Mapped[int] = mapped_column(
        ForeignKey("vector_collections.id", ondelete="CASCADE")
    )

    vector_collection: Mapped["VectorCollections"] = relationship(
        back_populates="documents"
    )


class VectorCollections(Base):
    __tablename__ = "vector_collections"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 对外暴露的标识符
    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    display_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 多用户情况下可以不设置 unique=True
    collection_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    documents: Mapped[list["Documents"]] = relationship(
        back_populates="vector_collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    threads: Mapped[list["ThreadCollectionAssociation"]] = relationship(
        back_populates="collection"
    )


class WorkspaceThreads(Base):
    __tablename__ = "workspace_threads"

    id: Mapped[int] = mapped_column(primary_key=True)

    uid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    workspace_thread_name: Mapped[str]
    chat_model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    chats: Mapped[list["WorkspaceChats"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )
    collections: Mapped[list["ThreadCollectionAssociation"]] = relationship(
        back_populates="thread"
    )


class ThreadCollectionAssociation(Base):
    __tablename__ = "thread_collection_association"

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_threads.id"), primary_key=True
    )
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("vector_collections.id"), primary_key=True
    )

    thread: Mapped["WorkspaceThreads"] = relationship(back_populates="collections")
    collection: Mapped["VectorCollections"] = relationship(back_populates="threads")


class WorkspaceChats(Base):
    __tablename__ = "workspace_chats"

    id: Mapped[int] = mapped_column(primary_key=True)

    role: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_threads.id", ondelete="CASCADE")
    )

    thread: Mapped["WorkspaceThreads"] = relationship(back_populates="chats")
